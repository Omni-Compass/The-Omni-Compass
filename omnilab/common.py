"""Shared pieces for the problem-map muscles (omnilab/*).

Every muscle is a simulation with three kinds of arm:
  native*          today's best tool for that problem, configured as documented by its project (named per muscle)
  omni             the same plant with Omni-Compass deciding: the frozen six-state engine (omnicompass.core, via
                   adapter.Governor) evolves on the muscle's observations; the muscle maps engine state to actions
  omni_no_engine   identical mapping with the engine's equations not evolved (Governor(evolve=False)): what the
                   mapping alone does, so the engine's own contribution is visible
Nothing in omnicompass/ is changed. Gauges are per muscle; every gauge has a direction (lower or higher is better).
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Dict, List

import numpy as np

from omnicompass.adapter import Governor, mode_law, AUTOPILOT


class Engine:
    """The frozen engine as a sensor-fusion and gating element.

    step(**obs) takes the adapter's observation names (queue_ratio, load_ratio, power_stress, thermal, network_stress,
    drift_ratio, stale, security_block) and returns the governor directive; .x is the evolved state
    (E, U, I_U, S, B, B_dot) and .push the equation (2) control effort (<= 0 means the engine reports convergence).
    """

    def __init__(self, evolve: bool = True, **law):
        base = mode_law("throughput")
        self.g = Governor(law=replace(base, **law) if law else base, evolve=evolve)
        self.g.set_mode(AUTOPILOT)

    def step(self, nodes: int = 20, cap: float = 1.0, **obs) -> Dict:
        self.g.nodes = max(1, int(nodes)); self.g.current_cap = cap
        return self.g.step(obs, 0)

    @property
    def x(self):
        return self.g.x

    @property
    def push(self) -> float:
        return self.g.last_push


def engine_for(arm: str, **law) -> Engine:
    return Engine(evolve=(arm != "omni_no_engine"), **law)


def mmc_ms(s_ms: float, u: float, c: float) -> float:
    """Response time of an M/M/c queue, Sakasegawa's approximation; u clipped at 0.99."""
    c = max(1.0, c); u = min(0.99, max(0.0, u))
    return s_ms * (1.0 + (u ** (math.sqrt(2.0 * (c + 1.0)) - 1.0) / (c * (1.0 - u)) if u > 0 else 0.0))


def wpct(vals, wts, q) -> float:
    v = np.asarray(vals, float); w = np.asarray(wts, float)
    if len(v) == 0:
        return 0.0
    if w.sum() <= 0:
        return float(np.percentile(v, q))
    o = np.argsort(v); v, w = v[o], w[o]
    cw = np.cumsum(w) / w.sum()
    return float(v[min(len(v) - 1, int(np.searchsorted(cw, q / 100.0)))])


def diurnal(rng, steps, per_day, mean, amp, bursts=0, burst_mag=1.0, burst_len=(10, 120), noise=0.05):
    t = np.arange(steps)
    s = mean * (1.0 + amp * np.sin(2 * math.pi * (t / per_day + rng.uniform(0, 1))))
    s = s * (1.0 + noise * rng.standard_normal(steps))
    for _ in range(bursts):
        c = int(rng.integers(0, steps)); w = int(rng.integers(*burst_len))
        s[c:c + w] += mean * burst_mag * rng.uniform(0.5, 1.5)
    return np.clip(s, 0.0, None)


def paired(native: List[Dict], omni: List[Dict], gauges: Dict[str, str], rng_seed: int = 7) -> Dict:
    """Per gauge: means, relative change (positive = better), paired bootstrap 95% CI of the difference, verdict."""
    rng = np.random.default_rng(rng_seed); out = {}
    for g, direction in gauges.items():
        a = np.array([r[g] for r in native], float); b = np.array([r[g] for r in omni], float)
        d = b - a
        bs = d[rng.integers(0, len(d), (4000, len(d)))].mean(1)
        lo, hi = (float(x) for x in np.percentile(bs, [2.5, 97.5]))
        ma, mb = float(a.mean()), float(b.mean())
        if abs(ma) > 1e-12:
            rel = (ma - mb) / abs(ma) if direction == "lower" else (mb - ma) / abs(ma)
        else:
            rel = 0.0 if abs(mb) < 1e-12 else (-1.0 if direction == "lower" else 1.0)
        better = (hi < 0) if direction == "lower" else (lo > 0)
        worse = (lo > 0) if direction == "lower" else (hi < 0)
        out[g] = {"native": ma, "omni": mb, "better_by": rel, "ci95": [lo, hi],
                  "verdict": "better" if better else "worse" if worse else ("tie" if np.allclose(a, b) else "not significant")}
    return out
