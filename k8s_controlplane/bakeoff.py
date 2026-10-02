# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Bake-off: Omni vs the covering public governor set.

Covering set used in autoscaler papers:
  HPA v2          industry default
  PID             control-theory default
  deadband        two-point threshold

Same metric stream, same replica bounds, same 15 s tick.
Recorded: PlanetLab capture.
Archetypes: smooth, burst, bimodal, diurnal, flash, ramp (synthetic shapes).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, List

import numpy as np

from omnicompass.adapter import AUTOPILOT, OBSERVE, AllocationLaw, Governor

from .config import HPAConfig
from .hpa import HorizontalPodAutoscaler
from .mechanism_harness import load_capture, obs_from_row

ROOT = Path(__file__).resolve().parent
CAPTURE = ROOT / "fixtures" / "METRICS_SERVER_CAPTURE.csv"
LO, HI = 1, 40
DT = 15


class PID:
    """Discrete PID on (metric - target). Output is replica increment."""

    def __init__(self, target=0.70, kp=8.0, ki=0.15, kd=2.0):
        self.target = target
        self.kp, self.ki, self.kd = kp, ki, kd
        self.i = 0.0
        self.prev = 0.0
        self.r = 4

    def step(self, now, current, metric):
        e = metric - self.target
        self.i = max(-4.0, min(4.0, self.i + e))
        d = e - self.prev
        self.prev = e
        u = self.kp * e + self.ki * self.i + self.kd * d
        self.r = int(np.clip(round(current + u), LO, HI))
        return self.r


class Deadband:
    def __init__(self, lo=0.50, hi=0.80):
        self.lo, self.hi = lo, hi
        self.r = 4

    def step(self, now, current, metric):
        if metric > self.hi:
            self.r = min(HI, current + max(1, current // 2))
        elif metric < self.lo:
            self.r = max(LO, current - max(1, current // 4))
        else:
            self.r = current
        return self.r


def hpa_ctrl(target=0.70):
    h = HorizontalPodAutoscaler(HPAConfig(target=target, min_replicas=LO, max_replicas=HI))

    def step(now, current, metric):
        return h.step(now, current, metric)

    return step


def omni_target_ctrl():
    gov = Governor(law=AllocationLaw(), evolve=True)
    gov.set_mode(AUTOPILOT)
    gov.nodes = 10
    gov.current_cap = 1.0
    h = HorizontalPodAutoscaler(HPAConfig(target=0.70, min_replicas=LO, max_replicas=HI))

    def step(now, current, metric):
        o = {
            "queue_ratio": max(0.0, metric - 0.70),
            "load_ratio": min(2.0, metric / 0.70) if metric else 0.0,
            "power_stress": min(1.5, metric),
            "thermal": min(1.5, 0.30 + 0.40 * metric),
            "network_stress": 0.0,
            "drift_ratio": 0.0,
            "stale": 0.0,
            "security_block": 0.0,
        }
        d = gov.step(o, 0)
        h.target = float(d["demand"])
        gov.nodes = max(8, min(40, gov.nodes + int(d["node_delta"])))
        gov.current_cap = float(d["power_cap"])
        return h.step(now, current, metric)

    return step


def omni_observe_ctrl():
    gov = Governor(law=AllocationLaw(), evolve=True)
    gov.set_mode(OBSERVE)
    h = HorizontalPodAutoscaler(HPAConfig(target=0.70, min_replicas=LO, max_replicas=HI))

    def step(now, current, metric):
        o = {
            "queue_ratio": max(0.0, metric - 0.70),
            "load_ratio": min(2.0, metric / 0.70) if metric else 0.0,
            "power_stress": min(1.5, metric),
            "thermal": min(1.5, 0.30 + 0.40 * metric),
            "network_stress": 0.0,
            "drift_ratio": 0.0,
            "stale": 0.0,
            "security_block": 0.0,
        }
        gov.step(o, 0)
        return h.step(now, current, metric)

    return step


def score(metrics: np.ndarray, replicas: List[int], target=0.70) -> dict:
    r = np.array(replicas, dtype=float)
    changes = int(np.sum(np.abs(np.diff(r)) > 0))
    hours = len(r) * DT / 3600.0
    replica_hours = float(np.sum(r) * DT / 3600.0)
    over = float(np.mean(metrics > target * 1.10))
    under = float(np.mean(metrics < target * 0.50))
    energy = float(np.sum((0.08 + 0.04 * r) * (DT / 3600.0)))
    return {
        "hours": hours,
        "replica_hours": replica_hours,
        "scale_events": changes,
        "mean_replicas": float(np.mean(r)),
        "max_replicas": int(np.max(r)),
        "frac_over_target": over,
        "frac_very_under": under,
        "energy_proxy_kwh": energy,
    }


def run_series(metrics: np.ndarray, factory: Callable) -> dict:
    step = factory()
    cur = 4
    path = []
    for i, m in enumerate(metrics):
        cur = int(step(i * DT, cur, float(m)))
        path.append(cur)
    return score(metrics, path)


def archetypes(n=5760) -> dict:
    """24 h @ 15 s. Shapes only. Not cluster traces."""
    t = np.arange(n) * DT / 3600.0
    rng = np.random.default_rng(7)
    return {
        "smooth": 0.55 + 0.10 * np.sin(2 * np.pi * t / 24.0),
        "burst": np.clip(0.25 + 0.70 * ((t % 6) < 0.5).astype(float), 0, 1.4),
        "bimodal": np.clip(0.20 + 0.55 * ((t % 12 < 3) | ((t % 12) > 8)).astype(float), 0, 1.3),
        "diurnal": np.clip(0.15 + 0.65 * np.maximum(0, np.sin(2 * np.pi * (t - 7) / 24.0)), 0, 1.2),
        "flash": np.clip(0.20 + 1.10 * ((t % 24) < 0.25).astype(float), 0, 1.6),
        "ramp": np.clip(0.15 + 0.035 * t, 0, 1.3),
        "noise": np.clip(0.40 + 0.25 * rng.normal(0, 1, n), 0.05, 1.2),
    }


def pid_ctrl():
    c = PID()
    return c.step


def deadband_ctrl():
    c = Deadband()
    return c.step


CONTROLLERS = {
    "hpa70": lambda: hpa_ctrl(0.70),
    "pid": pid_ctrl,
    "deadband": deadband_ctrl,
    "omni_observe": omni_observe_ctrl,
    "omni_target": omni_target_ctrl,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "BAKEOFF.json"))
    a = ap.parse_args()
    rows = []
    if CAPTURE.exists():
        series = load_capture(CAPTURE)
        for tid, recs in series.items():
            m = np.array([float(r["cpu_utilization"]) for r in recs])
            for name, fac in CONTROLLERS.items():
                s = run_series(m, fac)
                s.update({"suite": "planetlab", "trace": tid, "controller": name})
                rows.append(s)
    for name, m in archetypes().items():
        for cname, fac in CONTROLLERS.items():
            s = run_series(m, fac)
            s.update({"suite": "archetype", "trace": name, "controller": cname})
            rows.append(s)

    def agg(suite):
        out = {}
        sub = [r for r in rows if r["suite"] == suite]
        for c in CONTROLLERS:
            cs = [r for r in sub if r["controller"] == c]
            if not cs:
                continue
            out[c] = {
                k: float(np.mean([r[k] for r in cs]))
                for k in ("replica_hours", "scale_events", "mean_replicas",
                          "frac_over_target", "energy_proxy_kwh")
            }
            out[c]["n"] = len(cs)
        return out

    summary = {
        "benchmark": "HPA v2 + PID + deadband vs Omni, same 15s metric stream",
        "suites": {
            "planetlab_recorded": agg("planetlab"),
            "synthetic_archetypes": agg("archetype"),
        },
        "rows": rows,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(summary, indent=2))
    slim = {k: summary["suites"][k] for k in summary["suites"]}
    print(json.dumps({"benchmark": summary["benchmark"], "means": slim}, indent=2))


if __name__ == "__main__":
    main()
