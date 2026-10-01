"""Multi-workload Kubernetes fleet at 15-second resolution.

Workloads: synthetic CPU demand series calibrated to published fleet statistics (low mean utilization relative to
requests, diurnal cycle, AR(1) noise, bursts). Pods are placed by CPU request (first fit); actual CPU use is separate.
Node power follows the Cloud Carbon Footprint per-vCPU coefficients with a power-cap exponent for dynamic power.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

TICK_S = 15
W_MIN, W_MAX, W_MEM = 0.434, 1.948, 0.392


@dataclass(frozen=True)
class FleetConfig:
    workloads: int = 30
    hours: float = 6.0
    node_vcpu: int = 16
    node_gib: int = 64
    node_allocatable: float = 15.2
    pue: float = 1.18
    ca_boot_s: int = 180
    karpenter_boot_s: int = 60
    min_nodes: int = 2
    max_nodes: int = 80
    cap_exponent: float = 2.0
    healthy_served: float = 0.99

    @property
    def ticks(self) -> int:
        return int(self.hours * 3600 / TICK_S)


@dataclass
class Workload:
    name: str
    request: float
    min_replicas: int
    max_replicas: int
    demand: np.ndarray
    replicas: int = 2
    backlog: float = 0.0


def generate_workloads(cfg: FleetConfig, seed: int) -> List[Workload]:
    rng = np.random.default_rng(seed)
    T = cfg.ticks
    t = np.arange(T) * TICK_S / 3600.0
    out = []
    for w in range(cfg.workloads):
        base = float(rng.lognormal(mean=math.log(0.35), sigma=0.7))
        amp = float(rng.uniform(0.2, 0.6))
        phase = float(rng.uniform(0, 24))
        diurnal = 1.0 + amp * np.sin(2 * math.pi * (t + phase) / 24.0)
        noise = np.zeros(T); rho = 0.98; sd = float(rng.uniform(0.05, 0.2))
        e = rng.normal(0, sd * math.sqrt(1 - rho ** 2), T)
        for i in range(1, T):
            noise[i] = rho * noise[i - 1] + e[i]
        burst = np.ones(T)
        for _ in range(int(rng.poisson(1.2))):
            s = int(rng.integers(0, T)); d = int(rng.integers(40, 160)); burst[s:s + d] *= float(rng.uniform(2.0, 4.0))
        demand = np.maximum(0.02, base * diurnal * np.exp(noise) * burst)
        per_pod_p95 = float(np.percentile(demand, 95)) / 3.0
        request = float(np.clip(per_pod_p95 * rng.uniform(2.0, 5.0), 0.1, 4.0))
        out.append(Workload(f"w{w}", request, 2, 60, demand, replicas=3))
    return out


@dataclass
class Node:
    ready_at: int
    cap: float = 1.0
    pods: Dict[str, int] = field(default_factory=dict)
    added_at: int = 0


class Fleet:
    def __init__(self, cfg: FleetConfig, workloads: List[Workload]):
        self.cfg = cfg
        self.w = {x.name: x for x in workloads}
        self.nodes: List[Node] = []
        self.pending: Dict[str, int] = {}
        need = sum(x.request * x.replicas for x in workloads)
        for _ in range(max(cfg.min_nodes, math.ceil(need / (cfg.node_allocatable * 0.7)))):
            self.nodes.append(Node(ready_at=0))
        for x in workloads:
            self.pending[x.name] = x.replicas
        self.schedule(0)
        self.energy_wh = 0.0
        self.starts = 0
        self.stops = 0
        self.evictions = 0
        self.last_util = {x.name: 0.0 for x in workloads}

    def requested(self, n: Node) -> float:
        return sum(self.w[k].request * c for k, c in n.pods.items())

    def schedule(self, tick: int) -> None:
        for name in list(self.pending):
            need = self.pending[name]; req = self.w[name].request
            for n in self.nodes:
                while need > 0 and self.requested(n) + req <= self.cfg.node_allocatable + 1e-9:
                    n.pods[name] = n.pods.get(name, 0) + 1; need -= 1
                if need == 0:
                    break
            if need == 0:
                del self.pending[name]
            else:
                self.pending[name] = need

    def set_replicas(self, name: str, r: int) -> None:
        wl = self.w[name]
        r = max(wl.min_replicas, min(wl.max_replicas, r))
        cur = wl.replicas
        if r > cur:
            self.pending[name] = self.pending.get(name, 0) + (r - cur)
        elif r < cur:
            drop = cur - r
            p = min(drop, self.pending.get(name, 0))
            if p:
                self.pending[name] -= p; drop -= p
                if self.pending[name] == 0:
                    del self.pending[name]
            for n in sorted(self.nodes, key=lambda n: self.requested(n)):
                while drop > 0 and n.pods.get(name, 0) > 0:
                    n.pods[name] -= 1; drop -= 1
                    if n.pods[name] == 0:
                        del n.pods[name]
        wl.replicas = r

    def add_nodes(self, k: int, tick: int, boot_s: int) -> None:
        for _ in range(max(0, min(k, self.cfg.max_nodes - len(self.nodes)))):
            self.nodes.append(Node(ready_at=tick + boot_s // TICK_S, added_at=tick)); self.starts += 1

    def remove_node(self, n: Node) -> None:
        for k, c in n.pods.items():
            self.pending[k] = self.pending.get(k, 0) + c; self.evictions += c
        self.nodes.remove(n); self.stops += 1

    def step(self, tick: int) -> Dict[str, float]:
        cfg = self.cfg
        self.schedule(tick)
        placed: Dict[str, list] = {k: [] for k in self.w}
        for n in self.nodes:
            if n.ready_at <= tick:
                for k, c in n.pods.items():
                    placed[k].append((n, c))
        demand_total = served_total = 0.0
        node_use = {id(n): 0.0 for n in self.nodes}
        worst = 1.0
        dmd = {}
        for name, wl in self.w.items():
            base = float(wl.demand[tick])
            d = base + wl.backlog
            dmd[name] = d
            demand_total += base
            running = sum(c for _, c in placed[name])
            if running == 0:
                self.last_util[name] = 0.0
                continue
            per_pod = d / max(1, wl.replicas)
            for n, c in placed[name]:
                node_use[id(n)] += per_pod * c
            self.last_util[name] = (d / running) / wl.request
        frac = {}
        for n in self.nodes:
            capc = cfg.node_vcpu * n.cap if n.ready_at <= tick else 0.0
            u = node_use[id(n)]
            frac[id(n)] = 1.0 if u <= capc or u == 0 else capc / u
        for name, wl in self.w.items():
            d = dmd[name]
            running = sum(c for _, c in placed[name])
            if running == 0:
                wl.backlog = min(d, 50.0 * float(wl.demand[tick]) + 1.0)
                worst = 0.0
                continue
            per_pod = d / max(1, wl.replicas)
            served = min(d, sum(per_pod * c * frac[id(n)] for n, c in placed[name]))
            wl.backlog = max(0.0, d - served)
            served_total += served
            worst = min(worst, served / max(1e-9, d))
        power = busy = 0.0
        for n in self.nodes:
            if n.ready_at > tick:
                power += cfg.node_vcpu * W_MIN + cfg.node_gib * W_MEM
                continue
            capc = cfg.node_vcpu * n.cap
            util = min(1.0, node_use[id(n)] / cfg.node_vcpu)
            busy += min(node_use[id(n)], capc)
            power += cfg.node_vcpu * (W_MIN + util * (W_MAX - W_MIN) * n.cap ** (cfg.cap_exponent - 1.0)) + cfg.node_gib * W_MEM
        power *= cfg.pue
        self.energy_wh += power * TICK_S / 3600.0
        self.node_use = node_use
        cap_total = sum(cfg.node_vcpu * n.cap for n in self.nodes if n.ready_at <= tick)
        return {"demand": demand_total, "served": served_total, "worst_served": worst, "power_w": power,
                "capacity": cap_total, "busy": busy, "backlog": sum(x.backlog for x in self.w.values()),
                "pending": sum(self.pending.values()), "nodes": len(self.nodes)}
