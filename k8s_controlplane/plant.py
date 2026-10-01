"""Homogeneous-node cluster plant at the harness tick.

Packing is by CPU request (CA view). Delivered work is limited by ready
nodes' actual cores and by running Ready replicas. Nodes boot after a delay.
New replicas become Ready after metrics.readiness_s.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .config import HarnessConfig


@dataclass
class Boot:
    ready_at_s: int
    kind: str = "node"


@dataclass
class Plant:
    cfg: HarnessConfig
    ready_nodes: int
    desired_replicas: int
    running_replicas: int
    ready_replicas: int
    queue: float = 0.0
    thermal: float = 0.32
    power_cap: float = 1.0
    boots: List[Boot] = field(default_factory=list)
    replica_ready_at: List[int] = field(default_factory=list)
    last_nodes: int = 0
    parked: int = 0

    @classmethod
    def new(cls, cfg: HarnessConfig) -> "Plant":
        p = cfg.plant
        return cls(
            cfg=cfg,
            ready_nodes=p.initial_nodes,
            desired_replicas=p.initial_replicas,
            running_replicas=p.initial_replicas,
            ready_replicas=p.initial_replicas,
            last_nodes=p.initial_nodes,
        )

    @property
    def booting(self) -> int:
        return sum(1 for b in self.boots if b.kind == "node")

    @property
    def total_nodes(self) -> int:
        return self.ready_nodes + self.booting

    @property
    def pods_per_node(self) -> float:
        return self.cfg.plant.cores_per_node / self.cfg.plant.pod_request_cores

    @property
    def allocatable_pods(self) -> int:
        return int(self.ready_nodes * self.pods_per_node)

    def request_util(self) -> float:
        cap = max(1.0, self.ready_nodes * self.cfg.plant.cores_per_node)
        used = self.running_replicas * self.cfg.plant.pod_request_cores
        return min(2.0, used / cap)

    def schedule_nodes(self, target: int, now_s: int, ready_s: int) -> None:
        target = max(self.cfg.ca.min_nodes, min(self.cfg.ca.max_nodes, int(target)))
        pool = getattr(self.cfg, "pool", "elastic")
        if pool == "always_on":
            target = max(target, self.total_nodes)
        cur = self.total_nodes
        if pool == "idle_power" and target < cur:
            self.parked = min(self.ready_nodes - self.cfg.ca.min_nodes,
                              self.parked + (cur - target))
            return
        if target > cur and self.parked > 0:
            take = min(self.parked, target - cur)
            self.parked -= take
            if target - cur - take <= 0:
                return
            target = self.total_nodes + (target - cur - take)
        if target > cur:
            for _ in range(target - cur):
                self.boots.append(Boot(now_s + ready_s, "node"))
        elif target < cur:
            drop = cur - target
            live_boot = [b for b in self.boots if b.kind == "node"]
            cancel = min(drop, len(live_boot))
            if cancel:
                self.boots = [b for b in self.boots if b.kind != "node"][cancel:]
                drop -= cancel
            self.ready_nodes = max(self.cfg.ca.min_nodes, self.ready_nodes - drop)

    def set_replicas(self, desired: int, now_s: int) -> None:
        desired = max(self.cfg.hpa.min_replicas, min(self.cfg.hpa.max_replicas, int(desired)))
        self.desired_replicas = desired

    def tick(self, now_s: int, src: dict) -> dict:
        p = self.cfg.plant
        dt_h = p.dt_s / 3600.0
        still = []
        for b in self.boots:
            if now_s >= b.ready_at_s and b.kind == "node":
                self.ready_nodes += 1
            else:
                still.append(b)
        self.boots = still

        failed = int(round(p.initial_nodes * src["failed_frac"]))
        avail = max(self.cfg.ca.min_nodes, self.ready_nodes - failed)
        pack = int(avail * self.pods_per_node)
        self.running_replicas = min(self.desired_replicas, pack)
        pending = max(0, self.desired_replicas - self.running_replicas)

        if self.running_replicas > self.ready_replicas:
            self.ready_replicas = min(
                self.running_replicas,
                self.ready_replicas + max(1, int(p.dt_s / max(1, self.cfg.metrics.readiness_s) * 8)),
            )
        else:
            self.ready_replicas = self.running_replicas

        nominal = p.initial_nodes * p.cores_per_node
        demand_cores = (src["demand"] + src["batch"]) * nominal * src["rollout"]
        self.queue += demand_cores * (p.dt_s / 60.0)

        throttle = min(1.0, max(0.58, 1.0 - max(0.0, self.thermal - 0.82) * 0.65))
        cpu_budget = avail * p.cores_per_node * self.power_cap * throttle
        replica_budget = self.ready_replicas * p.pod_request_cores * 1.35
        delivered = min(self.queue, max(0.0, min(cpu_budget, replica_budget) * (p.dt_s / 60.0)))
        self.queue -= delivered

        util_node = min(1.25, delivered / max(1e-9, avail * p.cores_per_node * (p.dt_s / 60.0)))
        if self.ready_replicas > 0:
            usage_per_pod = delivered / max(1e-9, self.ready_replicas * (p.dt_s / 60.0))
            true_hpa = min(2.0, usage_per_pod / max(1e-9, p.pod_request_cores))
        else:
            true_hpa = 0.0

        parked = max(0, min(self.parked, self.ready_nodes))
        active = max(0, self.ready_nodes - parked)
        pkw = (
            active * (p.node_idle_kw + p.node_dynamic_kw * min(1.0, util_node))
            + parked * p.node_idle_kw
        ) * p.pue * self.power_cap
        pstress = pkw / max(1e-9, p.site_power_kw * src["power_derate"])
        self.thermal = min(1.35, max(0.0, 0.86 * self.thermal + 0.14 * (0.34 + 0.62 * min(1.35, pstress))))

        qratio = min(2.0, self.queue / max(1.0, cpu_budget * 2.0))
        lratio = min(2.0, demand_cores / max(1.0, cpu_budget))
        return {
            "demand_cores": demand_cores,
            "delivered_cores": delivered / max(1e-9, p.dt_s / 60.0),
            "true_hpa_metric": true_hpa,
            "request_util": self.request_util(),
            "pending_pods": pending,
            "queue": self.queue,
            "queue_ratio": qratio,
            "load_ratio": lratio,
            "power_kw": pkw,
            "power_stress": pstress,
            "thermal": self.thermal,
            "ready_nodes": self.ready_nodes,
            "total_nodes": self.total_nodes,
            "desired_replicas": self.desired_replicas,
            "running_replicas": self.running_replicas,
            "ready_replicas": self.ready_replicas,
            "security": src["security"],
            "event": src["event"],
        }
