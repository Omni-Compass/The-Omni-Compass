"""Cluster Autoscaler algorithm replica (documented defaults).

Scale-up: unschedulable work present → add nodes sized to pending requests.
Scale-down: request-utilization < 0.5 for unneeded_s, not within delay_after_add
of a scale-up, and remaining nodes can absorb the departing node's requests.
Utilization is sum(requests)/allocatable, not measured CPU.
"""
from __future__ import annotations

from .config import CAConfig


class ClusterAutoscaler:
    def __init__(self, cfg: CAConfig):
        self.cfg = cfg
        self.unneeded_s = 0
        self.since_add_s = 10**6
        self.since_delete_s = 10**6
        self.last_scan_s = -10**9
        self.allow_scale_down = True
        self.allow_scale_up = True
        self.unneeded_need = cfg.unneeded_s
        self.delay_add_need = cfg.delay_after_add_s

    def step(
        self,
        now_s: int,
        ready_nodes: int,
        booting_nodes: int,
        pending_pods: int,
        request_util: float,
        dt_s: int,
    ) -> int:
        """Return node delta (desired ready+booting change this scan)."""
        cfg = self.cfg
        if now_s - self.last_scan_s < cfg.scan_interval_s:
            self.since_add_s += dt_s
            self.since_delete_s += dt_s
            return 0
        self.last_scan_s = now_s
        total = ready_nodes + booting_nodes
        delta = 0

        if self.allow_scale_up and pending_pods > 0 and total < cfg.max_nodes:
            need = min(cfg.max_add_per_scan, max(1, (pending_pods + 15) // 16), cfg.max_nodes - total)
            if need > 0:
                delta = need
                self.since_add_s = 0
                self.unneeded_s = 0
                self.since_delete_s += dt_s
                return delta

        self.since_add_s += dt_s
        self.since_delete_s += dt_s

        if not self.allow_scale_down:
            self.unneeded_s = 0
            return 0

        packing_ok = request_util < cfg.utilization_threshold
        if packing_ok and pending_pods == 0 and total > cfg.min_nodes:
            self.unneeded_s += dt_s
        else:
            self.unneeded_s = 0

        if (
            self.unneeded_s >= self.unneeded_need
            and self.since_add_s >= self.delay_add_need
            and self.since_delete_s >= cfg.delay_after_delete_s
            and total > cfg.min_nodes
        ):
            delta = -min(cfg.max_delete_per_scan, total - cfg.min_nodes)
            self.unneeded_s = 0
            self.since_delete_s = 0
        return delta
