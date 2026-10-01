"""Kubernetes autoscaling controllers (documented behaviour) and the Omni-Compass bridge for the fleet plant.

HPA (kubernetes.io, Horizontal Pod Autoscaling): desired = ceil(current * utilization / target); no change while
  |ratio - 1| <= 0.1; scale-down uses the highest recommendation of the last 300 s; scale-up limited to
  max(4 pods, 100%) per 15 s. Utilization is read from the previous tick (metrics-server scrape lag).
Cluster Autoscaler (kubernetes/autoscaler FAQ): scale-up for unschedulable pods (boot 180 s); a node whose requested
  CPU is below 50% of allocatable for 10 minutes, whose pods fit elsewhere, and which is not within 10 minutes of a
  scale-up, is removed (one per scan).
Karpenter-lite: provisioning for unschedulable pods (boot 60 s); every 60 s, one node older than 5 minutes whose pods
  fit on the remaining nodes is consolidated.
Coordinated request sizing (Omni): as VPA-lite, restricted to workloads at minimum replicas, and never below
  p99 per-pod usage / (0.9 x HPA target), so that the resized request cannot move the HPA outside its tolerance band.
VPA-lite: every 30 minutes, request = 1.15 x p90 of per-pod usage over the elapsed window, applied when it differs
  by more than 10% (the Kubernetes documentation advises against combining HPA and VPA on CPU; the arm is included
  as an aggressive request right-sizing baseline).
"""
from __future__ import annotations

import math
from typing import Dict, List

import numpy as np

from .plant import Fleet, TICK_S


class HPA:
    def __init__(self, target: float = 0.7):
        self.target = target
        self.hist: Dict[str, List[int]] = {}

    def step(self, f: Fleet, tick: int) -> None:
        for name, wl in f.w.items():
            util = f.last_util[name]
            cur = wl.replicas
            ratio = util / max(1e-9, self.target)
            rec = cur if abs(ratio - 1.0) <= 0.1 else math.ceil(cur * ratio)
            rec = max(wl.min_replicas, min(wl.max_replicas, rec))
            h = self.hist.setdefault(name, [])
            h.append(rec); del h[:-20]
            want = rec if rec >= cur else max(h)
            want = min(want, cur + max(4, cur))
            if want != cur:
                f.set_replicas(name, want)


def _fits_elsewhere(f: Fleet, n, tick: int) -> bool:
    free = [f.cfg.node_allocatable - f.requested(m) for m in f.nodes if m is not n and m.ready_at <= tick]
    for k, c in sorted(n.pods.items(), key=lambda kv: -f.w[kv[0]].request):
        r = f.w[k].request
        for _ in range(c):
            j = next((i for i, fr in enumerate(free) if fr >= r - 1e-9), None)
            if j is None:
                return False
            free[j] -= r
    return True


def _pending_nodes(f: Fleet, tick: int) -> int:
    req = sum(f.w[k].request * c for k, c in f.pending.items())
    booting_free = sum(f.cfg.node_allocatable - f.requested(n) for n in f.nodes if n.ready_at > tick)
    return max(0, math.ceil((req - booting_free) / f.cfg.node_allocatable - 1e-9)) if req > 0 else 0


class ClusterAutoscaler:
    def __init__(self):
        self.under: Dict[int, int] = {}
        self.last_add = -10 ** 9

    def step(self, f: Fleet, tick: int) -> None:
        k = _pending_nodes(f, tick)
        if k > 0:
            f.add_nodes(k, tick, f.cfg.ca_boot_s); self.last_add = tick
            return
        if tick - self.last_add < 600 // TICK_S or len(f.nodes) <= f.cfg.min_nodes:
            return
        for n in list(f.nodes):
            if n.ready_at > tick:
                continue
            key = id(n)
            if f.requested(n) < 0.5 * f.cfg.node_allocatable:
                self.under[key] = self.under.get(key, 0) + 1
            else:
                self.under[key] = 0
        for n in sorted(f.nodes, key=lambda n: f.requested(n)):
            if n.ready_at <= tick and self.under.get(id(n), 0) >= 600 // TICK_S and _fits_elsewhere(f, n, tick):
                f.remove_node(n); self.under.pop(id(n), None); f.schedule(tick)
                return


class Karpenter:
    def __init__(self, min_age_s: int = 300):
        self.min_age = min_age_s // TICK_S

    def step(self, f: Fleet, tick: int) -> None:
        k = _pending_nodes(f, tick)
        if k > 0:
            f.add_nodes(k, tick, f.cfg.karpenter_boot_s)
            return
        if tick % 4 or len(f.nodes) <= f.cfg.min_nodes:
            return
        for n in sorted(f.nodes, key=lambda n: f.requested(n)):
            if n.ready_at <= tick and tick - n.added_at >= self.min_age and _fits_elsewhere(f, n, tick):
                f.remove_node(n); f.schedule(tick)
                return


class RequestSizer:
    """Per-pod p-quantile usage x (1 + margin), every `period_s`, applied on > `band` relative change."""

    def __init__(self, q: float = 90.0, margin: float = 0.15, period_s: int = 1800, band: float = 0.10, floor: float = 0.05,
                 only_at_min: bool = False):
        self.q, self.margin, self.period, self.band, self.floor = q, margin, period_s // TICK_S, band, floor
        self.only_at_min = only_at_min
        self.samples: Dict[str, List[float]] = {}
        self.changes = 0

    def observe(self, f: Fleet, tick: int) -> None:
        for name, wl in f.w.items():
            self.samples.setdefault(name, []).append(float(wl.demand[tick]) / max(1, wl.replicas))

    def step(self, f: Fleet, tick: int, allow: bool = True, hpa_target: float = 0.0) -> None:
        self.observe(f, tick)
        if tick == 0 or tick % self.period or not allow:
            return
        for name, wl in f.w.items():
            if self.only_at_min and wl.replicas > wl.min_replicas:
                continue
            new = max(self.floor, float(np.percentile(self.samples[name], self.q)) * (1.0 + self.margin))
            if hpa_target > 0.0:
                new = max(new, float(np.percentile(self.samples[name], 99)) * wl.replicas / max(1, wl.replicas) / (hpa_target * 0.9))
            if abs(new - wl.request) > self.band * wl.request:
                wl.request = new; self.changes += 1
                for n in f.nodes:
                    while f.requested(n) > f.cfg.node_allocatable + 1e-9 and n.pods.get(name, 0) > 0:
                        n.pods[name] -= 1; f.pending[name] = f.pending.get(name, 0) + 1; f.evictions += 1
                        if n.pods[name] == 0:
                            del n.pods[name]
