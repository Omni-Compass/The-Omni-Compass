"""Fleet control-plane harness at 15-second resolution.

Plant: homogeneous node pools, workloads with CPU requests and actual usage, fluid request packing, per-workload
backlog, node boot delay (identical for every arm), power (idle + dynamic x utilization, scaled by power cap, PUE),
first-order thermal response, site power limit.

Execution layer (documented behaviour, not the upstream binaries):
  metrics-server   per-workload usage / request, published every 15 s from the previous tick (15 s lag)
  HPA              desired = ceil(current * metric / target); no change while |ratio - 1| <= 0.1; scale-up limited to
                   max(4 pods, 100%) per 15 s; scale-down uses the highest recommendation in the last 300 s
  ClusterAutoscaler  scan every 10 s (every tick here): add nodes for pending requests; remove one node when request
                   utilization < 0.5 for 10 min, not within 10 min of a scale-up
  Karpenter-lite   add exactly the nodes pending requests need; remove a node whenever the remaining nodes hold all
                   requests at <= 0.9 packing, checked every 30 s
Vessels:
  web        HPA-scaled services, diurnal load with bursts
  batch      job queue (no HPA): jobs request cores for a duration
  gpu        long training jobs on 8-GPU nodes, high power per node
  gpu_always_on  as gpu, but powering a node off is not permitted (training runs cannot be interrupted):
             controllers may only park idle nodes (Ready, drawing park_frac x idle power) and set power caps
  multi      four web clusters sharing one site power budget
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

TICK = 15.0
STEPS = 1440
BOOT_TICKS = 6


@dataclass
class Workload:
    name: str
    request: float
    min_rep: int
    max_rep: int
    demand: np.ndarray
    hpa: bool = True
    replicas: int = 0
    backlog: float = 0.0
    served: float = 0.0
    rec_hist: List[int] = field(default_factory=list)
    metric: float = 0.0


@dataclass
class Pool:
    cores: float
    idle_kw: float
    dyn_kw: float
    nodes: int
    min_nodes: int
    max_nodes: int
    booting: List[int] = field(default_factory=list)
    cap: float = 1.0
    thermal: float = 0.35
    parked: int = 0
    power_off: bool = True
    park_frac: float = 0.25


@dataclass
class Cluster:
    workloads: List[Workload]
    pool: Pool
    ca_under: int = 0
    ca_since_add: int = 999


@dataclass
class Scenario:
    vessel: str
    seed: int
    clusters: List[Cluster]
    site_limit_kw: float
    pue: float = 1.2


def _series(rng, steps, mean, amp, bursts, burst_mag, noise):
    t = np.arange(steps) * TICK / 3600.0
    phase = rng.uniform(0, 24)
    base = mean * (1.0 + amp * np.sin(2 * math.pi * (t + phase) / 24.0))
    s = base * (1.0 + noise * rng.standard_normal(steps))
    for _ in range(bursts):
        c = rng.integers(0, steps); w = rng.integers(20, 240)
        s[c:c + w] += mean * burst_mag * rng.uniform(0.5, 1.5)
    return np.clip(s, 0.0, None)


def make_scenario(vessel: str, seed: int) -> Scenario:
    rng = np.random.default_rng(seed)
    if vessel in ("web", "multi"):
        n_clusters = 4 if vessel == "multi" else 1
        clusters = []
        for c in range(n_clusters):
            wls = []
            for i in range(12):
                req = float(rng.choice([0.25, 0.5, 1.0, 2.0]))
                peak_pods = int(rng.integers(4, 30))
                mean_cores = req * peak_pods * rng.uniform(0.15, 0.35)
                d = _series(rng, STEPS, mean_cores, rng.uniform(0.2, 0.6), int(rng.integers(0, 4)), rng.uniform(1.0, 3.0), 0.08)
                wls.append(Workload(f"c{c}w{i}", req, 2, peak_pods * 3, d))
            clusters.append(Cluster(wls, Pool(32.0, 0.20, 0.35, 12, 3, 60)))
        limit = (38.0 if vessel == "web" else 130.0) * rng.uniform(0.9, 1.1)
    elif vessel == "batch":
        steps = STEPS
        arrivals = rng.poisson(rng.uniform(0.15, 0.35), steps)
        d = np.zeros(steps)
        for t, k in enumerate(arrivals):
            for _ in range(k):
                dur = int(rng.integers(20, 400)); cores = float(rng.choice([4, 8, 16, 32]))
                d[t:t + dur] += cores
        wls = [Workload("jobs", 1.0, 0, 100000, d, hpa=False)]
        clusters = [Cluster(wls, Pool(64.0, 0.25, 0.45, 8, 1, 40))]
        limit = 30.0 * rng.uniform(0.9, 1.1)
    elif vessel in ("gpu", "gpu_always_on"):
        steps = STEPS
        d = np.zeros(steps)
        t = 0
        while t < steps:
            gap = int(rng.integers(10, 200)); t += gap
            dur = int(rng.integers(120, 900)); g = float(rng.choice([8, 16, 32]))
            d[t:t + dur] += g
        wls = [Workload("training", 1.0, 0, 100000, d, hpa=False)]
        clusters = [Cluster(wls, Pool(8.0, 0.60, 2.60, 4, 1, 12, power_off=(vessel == "gpu")))]
        limit = 34.0 * rng.uniform(0.9, 1.1)
    else:
        raise ValueError(vessel)
    for c in clusters:
        for w in c.workloads:
            if w.hpa:
                w.replicas = max(w.min_rep, int(math.ceil(w.demand[0] / (w.request * 0.7))))
    return Scenario(vessel, seed, clusters, limit)


def hpa_step(w: Workload, target: float) -> None:
    ratio = w.metric / max(target, 1e-9)
    cur = w.replicas
    rec = cur if abs(ratio - 1.0) <= 0.1 else max(w.min_rep, min(w.max_rep, int(math.ceil(cur * ratio))))
    w.rec_hist = (w.rec_hist + [rec])[-20:]
    new = min(rec, cur + max(4, cur)) if rec > cur else max(w.rec_hist)
    w.replicas = max(w.min_rep, min(w.max_rep, new))
