# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Horizontal Pod Autoscaler algorithm replica (documented defaults).

desiredReplicas = ceil(current * currentMetric / target)
Skip if |ratio - 1| <= tolerance.
Scale-down uses the highest recommendation in the stabilization window.
Scale-up window default is 0 (latest recommendation).
Rate: scale-up max(4 pods, 100% current) per 15s; scale-down 100% per 15s.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Deque, Tuple

from .config import HPAConfig


class HorizontalPodAutoscaler:
    def __init__(self, cfg: HPAConfig):
        self.cfg = cfg
        self.target = float(cfg.target)
        self._recs: Deque[Tuple[int, int]] = deque()
        self.last_sync_s = -10**9
        self.last_applied = cfg.min_replicas

    def recommend(self, current: int, metric: float) -> int:
        cfg = self.cfg
        current = max(1, int(current))
        if metric <= 0.0:
            rec = current
        else:
            ratio = metric / max(self.target, 1e-9)
            if abs(ratio - 1.0) <= cfg.tolerance:
                rec = current
            else:
                rec = int(math.ceil(current * ratio))
        return max(cfg.min_replicas, min(cfg.max_replicas, rec))

    def stabilize(self, now_s: int, rec: int, current: int) -> int:
        self._recs.append((now_s, rec))
        up_cut = now_s - self.cfg.scale_up_window_s
        down_cut = now_s - self.cfg.scale_down_window_s
        while self._recs and self._recs[0][0] < min(up_cut, down_cut) - self.cfg.scale_down_window_s:
            self._recs.popleft()
        if rec >= current:
            window = [r for t, r in self._recs if t > up_cut] or [rec]
            chosen = min(window) if self.cfg.scale_up_window_s > 0 else rec
        else:
            window = [r for t, r in self._recs if t > down_cut] or [rec]
            chosen = max(window)
        return max(self.cfg.min_replicas, min(self.cfg.max_replicas, chosen))

    def rate_limit(self, current: int, desired: int) -> int:
        if desired >= current:
            cap = max(self.cfg.scale_up_pods, int(math.ceil(current * self.cfg.scale_up_percent / 100.0)))
            return min(desired, current + max(0, cap))
        cap = int(math.ceil(current * self.cfg.scale_down_percent / 100.0))
        return max(desired, current - max(0, cap))

    def step(self, now_s: int, current_replicas: int, metric: float) -> int:
        if now_s - self.last_sync_s < self.cfg.sync_period_s:
            return self.last_applied
        self.last_sync_s = now_s
        rec = self.recommend(current_replicas, metric)
        stab = self.stabilize(now_s, rec, current_replicas)
        applied = self.rate_limit(current_replicas, stab)
        self.last_applied = applied
        return applied
