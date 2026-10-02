# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Karpenter-lite: provision on pending pods; consolidate empty/underutilized nodes.

Not the Karpenter disruption controller, scheduling simulation, or NodePool
weights. Documented-shape defaults: faster boot than CA, consolidateAfter,
disruption budget as a fraction of ready nodes per scan.
"""
from __future__ import annotations

from .config import KarpenterConfig


class KarpenterLite:
    def __init__(self, cfg: KarpenterConfig):
        self.cfg = cfg
        self.under_s = 0
        self.empty_s = 0
        self.last_s = -10**9

    def step(
        self,
        now_s: int,
        ready_nodes: int,
        booting_nodes: int,
        pending_pods: int,
        request_util: float,
        running_pods: int,
        pods_per_node: float,
        dt_s: int,
    ) -> int:
        cfg = self.cfg
        total = ready_nodes + booting_nodes
        if pending_pods > 0 and total < cfg.max_nodes:
            need = min(cfg.max_add_per_scan, max(1, (pending_pods + 15) // 16), cfg.max_nodes - total)
            self.under_s = self.empty_s = 0
            return need

        empty = running_pods <= max(0, (ready_nodes - 1) * pods_per_node * 0.05)
        if empty and total > cfg.min_nodes:
            self.empty_s += dt_s
            self.under_s = 0
            if self.empty_s >= cfg.empty_after_s:
                self.empty_s = 0
                return -1
        elif request_util < 0.50 and pending_pods == 0 and total > cfg.min_nodes:
            self.under_s += dt_s
            self.empty_s = 0
            budget = max(1, int(ready_nodes * cfg.disruption_budget_frac))
            if self.under_s >= cfg.consolidate_after_s:
                self.under_s = 0
                return -min(budget, total - cfg.min_nodes)
        else:
            self.under_s = self.empty_s = 0
        return 0
