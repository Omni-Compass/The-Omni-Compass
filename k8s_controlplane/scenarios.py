"""Scenario generator. Same family names as the Omni kit, retimed to seconds."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


FAMILIES = [
    ("normal_variation", 0.10),
    ("demand_spike", 0.18),
    ("node_rack_failure", 0.12),
    ("telemetry_fault", 0.10),
    ("alert_incident", 0.10),
    ("power_thermal_network", 0.12),
    ("security_policy", 0.08),
    ("deployment_rollout", 0.08),
    ("compound_failure", 0.12),
]


@dataclass
class Scenario:
    scenario_id: int
    seed: int
    family: str
    base_load: float
    spike: float
    event_start_s: int
    event_duration_s: int
    failed_frac: float
    metrics_drop: float
    power_derate: float
    security_p: float
    rollout_mult: float
    batch_frac: float


def generate(n: int, seed: int, duration_s: int) -> list[Scenario]:
    rng = np.random.default_rng(seed)
    names = []
    for name, w in FAMILIES:
        names.extend([name] * max(1, int(round(n * w))))
    while len(names) < n:
        names.append("normal_variation")
    names = names[:n]
    rng.shuffle(names)
    out = []
    for i, fam in enumerate(names):
        event_start = int(rng.integers(int(0.15 * duration_s), int(0.55 * duration_s)))
        event_dur = int(rng.integers(15 * 60, 45 * 60))
        sc = Scenario(
            scenario_id=i,
            seed=int(seed + i * 9973),
            family=fam,
            base_load=float(rng.uniform(0.42, 0.62)),
            spike=1.0,
            event_start_s=event_start,
            event_duration_s=event_dur,
            failed_frac=0.0,
            metrics_drop=0.0,
            power_derate=1.0,
            security_p=0.0,
            rollout_mult=1.0,
            batch_frac=0.0,
        )
        if fam == "demand_spike":
            sc.spike = float(rng.uniform(1.8, 2.6))
        elif fam == "node_rack_failure":
            sc.failed_frac = float(rng.uniform(0.15, 0.35))
            sc.spike = float(rng.uniform(1.1, 1.4))
        elif fam == "telemetry_fault":
            sc.metrics_drop = float(rng.uniform(0.15, 0.40))
        elif fam == "alert_incident":
            sc.spike = float(rng.uniform(1.5, 2.1))
            sc.batch_frac = float(rng.uniform(0.08, 0.18))
        elif fam == "power_thermal_network":
            sc.power_derate = float(rng.uniform(0.72, 0.90))
            sc.spike = float(rng.uniform(1.2, 1.7))
        elif fam == "security_policy":
            sc.security_p = float(rng.uniform(0.35, 0.80))
        elif fam == "deployment_rollout":
            sc.rollout_mult = float(rng.uniform(1.15, 1.35))
            sc.spike = float(rng.uniform(1.2, 1.6))
        elif fam == "compound_failure":
            sc.spike = float(rng.uniform(1.7, 2.4))
            sc.failed_frac = float(rng.uniform(0.10, 0.22))
            sc.power_derate = float(rng.uniform(0.80, 0.95))
            sc.metrics_drop = float(rng.uniform(0.05, 0.15))
        out.append(sc)
    return out


def source(scn: Scenario, t_s: int) -> dict:
    active = scn.event_start_s <= t_s < scn.event_start_s + scn.event_duration_s
    demand = scn.base_load
    failed = 0.0
    drop = 0.0
    derate = 1.0
    sec = 0.0
    roll = 1.0
    batch = 0.0
    if active:
        demand *= scn.spike
        failed = scn.failed_frac
        drop = scn.metrics_drop
        derate = scn.power_derate
        sec = scn.security_p
        roll = scn.rollout_mult
        batch = scn.batch_frac
    return {
        "demand": demand,
        "failed_frac": failed,
        "metrics_drop": drop,
        "power_derate": derate,
        "security": 1.0 if sec > 0.5 else 0.0,
        "rollout": roll,
        "batch": batch,
        "event": float(active),
    }
