"""Second HPA v2 implementation. Does not import hpa.py.

Used only to write status.desiredReplicas so agreement is not tautological.
Algorithm: kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale
defaults: tolerance 0.10, scale-down window 300s, scale-up window 0,
scale-up rate max(4, 100% current) / 15s, scale-down 100% / 15s.
"""
from __future__ import annotations

import math
from typing import List, Tuple


class IndependentHPA:
    def __init__(self, target=0.70, lo=1, hi=40, tol=0.10, down_win=300, period=15):
        self.target = float(target)
        self.lo = int(lo)
        self.hi = int(hi)
        self.tol = float(tol)
        self.down_win = int(down_win)
        self.period = int(period)
        self.hist: List[Tuple[int, int]] = []
        self.applied = lo
        self.last = -10**9

    def raw(self, current: int, metric: float) -> int:
        current = max(1, int(current))
        if metric <= 0.0:
            rec = current
        else:
            ratio = metric / max(self.target, 1e-12)
            rec = current if abs(ratio - 1.0) <= self.tol else int(math.ceil(current * ratio))
        return max(self.lo, min(self.hi, rec))

    def windowed(self, now: int, rec: int, current: int) -> int:
        self.hist.append((now, rec))
        cutoff = now - self.down_win
        self.hist = [(t, r) for t, r in self.hist if t >= cutoff]
        if rec >= current:
            return rec
        return max(r for _, r in self.hist)

    def rate(self, now: int, current: int, rec: int) -> int:
        if now - self.last < self.period:
            return self.applied
        if rec >= current:
            rec = min(rec, current + max(4, current))
        else:
            rec = max(rec, 0)
        self.applied = rec
        self.last = now
        return rec

    def step(self, now: int, current: int, metric: float) -> int:
        rec = self.raw(current, metric)
        rec = self.windowed(now, rec, current)
        return self.rate(now, current, rec)
