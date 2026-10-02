# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Metrics-server replica: lagged, Ready-pod-only average CPU utilization.

HPA resource utilization is usage/request, averaged over pods that have
reported. New replicas do not report until readiness_s. Optional random drops.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Tuple

import numpy as np

from .config import MetricsConfig


class MetricsServer:
    def __init__(self, cfg: MetricsConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self._buf: Deque[Tuple[int, float, int]] = deque()

    def observe(self, now_s: int, true_util: float, ready_replicas: int) -> None:
        if self.rng.random() < self.cfg.drop_probability:
            return
        self._buf.append((now_s, float(true_util), int(ready_replicas)))
        cutoff = now_s - self.cfg.report_lag_s - 4 * self.cfg.scrape_period_s
        while self._buf and self._buf[0][0] < cutoff:
            self._buf.popleft()

    def cpu_average_utilization(self, now_s: int) -> float:
        """Latest sample at least report_lag_s old. 0 if nothing Ready has reported."""
        ready_at = now_s - self.cfg.report_lag_s
        sample = None
        for t, util, n in reversed(self._buf):
            if t <= ready_at and n > 0:
                sample = util
                break
        return 0.0 if sample is None else float(sample)
