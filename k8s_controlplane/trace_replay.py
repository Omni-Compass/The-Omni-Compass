# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Replay recorded utilization traces through HPA + CA + Omni.

PlanetLab files are 5-minute CPU percent. Metrics-server scrapes every 15s, so
the open-loop replay holds the last recorded sample (same as a stale scrape).
That lag is declared, not hidden.

Modes
  open_loop   recorded util is the HPA metric. Replica count does not rewrite it.
  closed_loop recorded util shape drives plant demand; metric is produced by plant.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

import numpy as np

from .cluster_autoscaler import ClusterAutoscaler
from .config import HarnessConfig
from .hpa import HorizontalPodAutoscaler
from .omni_bridge import OmniLoop
from .plant import Plant

ROOT = Path(__file__).resolve().parent
TRACE_DIR = ROOT / "traces" / "planetlab"


def load_planetlab(path: Path) -> np.ndarray:
    xs = [float(x) for x in path.read_text().split() if x.strip()]
    return np.array(xs, dtype=float)


def resample_hold(series: np.ndarray, src_s: int, dst_s: int) -> np.ndarray:
    """Hold-last resample. PlanetLab 300s -> metrics-server 15s."""
    out = []
    t = 0
    end = int(len(series) * src_s)
    while t < end:
        i = min(len(series) - 1, t // src_s)
        out.append(series[i])
        t += dst_s
    return np.array(out, dtype=float)


def load_all() -> Dict[str, np.ndarray]:
    traces = {}
    for p in sorted(TRACE_DIR.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            traces[p.name] = load_planetlab(p)
    return traces


def replay_open_loop(name: str, util_pct: np.ndarray, arm: str, cfg: HarnessConfig) -> dict:
    """util_pct is 5-min CPU percent. HPA sees hold-last 15s metric = pct/100."""
    cfg.hpa.min_replicas = 1
    cfg.hpa.max_replicas = 40
    cfg.ca.min_nodes = 1
    cfg.ca.max_nodes = 20
    metric = resample_hold(util_pct / 100.0, 300, cfg.plant.dt_s)
    hpa = HorizontalPodAutoscaler(cfg.hpa)
    ca = ClusterAutoscaler(cfg.ca)
    omni = OmniLoop(arm, cfg) if arm.startswith("omni_") else None
    if omni and ("down" in arm or "full" in arm or "protect" in arm or "throughput" in arm):
        ca.allow_scale_down = False
    replicas = max(cfg.hpa.min_replicas, 4)
    nodes = 4
    energy = 0.0
    starts = stops = 0
    scale_up = scale_down = 0
    last_r = replicas
    last_n = nodes
    dt = cfg.plant.dt_s
    dt_h = dt / 3600.0
    for i, u in enumerate(metric):
        now = i * dt
        snap = {
            "queue_ratio": max(0.0, u - 0.7),
            "load_ratio": float(u),
            "power_stress": min(1.2, 0.4 + 0.5 * u),
            "thermal": 0.35 + 0.2 * u,
            "security": 0.0,
        }
        if omni is not None:
            d = omni.maybe_step(now, snap, 1.0, nodes)
            if omni.writes and d is not None and "observe" not in arm:
                hpa.target = float(d["demand"])
        new_r = hpa.step(now, replicas, float(u))
        pending = max(0, new_r - nodes * 4)
        req_util = (replicas * 0.5) / max(1.0, nodes * 8.0)
        nd = ca.step(now, nodes, 0, pending, req_util, dt)
        if omni is not None and omni.writes and d is not None and ("down" in arm or "full" in arm):
            nd = int(d["node_delta"]) if int(d.get("node_delta", 0)) < 0 else nd
        nodes = max(cfg.ca.min_nodes, min(cfg.ca.max_nodes, nodes + nd))
        replicas = new_r
        if replicas > last_r:
            scale_up += 1
        elif replicas < last_r:
            scale_down += 1
        starts += max(0, nodes - last_n)
        stops += max(0, last_n - nodes)
        last_r, last_n = replicas, nodes
        util_node = min(1.0, max(0.05, u))
        energy += nodes * (0.38 + 1.12 * util_node) * 1.18 * dt_h
    return {
        "trace": name,
        "arm": arm,
        "mode": "open_loop",
        "samples": int(len(metric)),
        "hours": len(metric) * dt / 3600.0,
        "mean_metric": float(np.mean(metric)),
        "peak_metric": float(np.max(metric)),
        "final_replicas": int(replicas),
        "final_nodes": int(nodes),
        "scale_up_events": scale_up,
        "scale_down_events": scale_down,
        "machines_started": starts,
        "machines_stopped": stops,
        "energy_kwh": energy,
        "mean_hpa_target": float(hpa.target),
    }


def replay_closed_loop(name: str, util_pct: np.ndarray, arm: str, cfg: HarnessConfig) -> dict:
    """Recorded shape is demand. Plant + metrics-server lag produce the HPA metric."""
    from .metrics_server import MetricsServer
    from .scenarios import Scenario

    series = resample_hold(util_pct / 100.0, 300, cfg.plant.dt_s)
    peak = max(float(np.max(series)), 1e-6)
    shape = series / peak
    cfg.hpa.min_replicas = 4
    cfg.hpa.max_replicas = 80
    rng = np.random.default_rng(1)
    plant = Plant.new(cfg)
    ms = MetricsServer(cfg.metrics, rng)
    hpa = HorizontalPodAutoscaler(cfg.hpa)
    ca = ClusterAutoscaler(cfg.ca)
    omni = OmniLoop(arm, cfg) if arm.startswith("omni_") else None
    energy = demand = work = 0.0
    starts = stops = 0
    last_n = plant.total_nodes
    dt = cfg.plant.dt_s
    for i, frac in enumerate(shape):
        now = i * dt
        src = {
            "demand": float(0.35 + 0.85 * frac),
            "failed_frac": 0.0,
            "metrics_drop": 0.0,
            "power_derate": 1.0,
            "security": 0.0,
            "rollout": 1.0,
            "batch": 0.0,
            "event": float(frac > 0.75),
        }
        snap = plant.tick(now, src)
        demand += snap["demand_cores"] * (dt / 60.0)
        work += snap["delivered_cores"] * (dt / 60.0)
        energy += snap["power_kw"] * (dt / 3600.0)
        ms.observe(now, snap["true_hpa_metric"], snap["ready_replicas"])
        metric = ms.cpu_average_utilization(now)
        if omni is not None:
            d = omni.maybe_step(now, snap, plant.power_cap, plant.ready_nodes)
            if omni.writes and d is not None and "observe" not in arm:
                hpa.target = float(d["demand"])
        plant.set_replicas(hpa.step(now, plant.running_replicas, metric), now)
        nd = ca.step(now, plant.ready_nodes, plant.booting, snap["pending_pods"], snap["request_util"], dt)
        plant.schedule_nodes(plant.total_nodes + nd, now, cfg.ca.node_ready_s)
        starts += max(0, plant.total_nodes - last_n)
        stops += max(0, last_n - plant.total_nodes)
        last_n = plant.total_nodes
    return {
        "trace": name,
        "arm": arm,
        "mode": "closed_loop",
        "samples": int(len(shape)),
        "hours": len(shape) * dt / 3600.0,
        "availability": work / max(1e-9, demand),
        "energy_kwh": energy,
        "final_replicas": plant.desired_replicas,
        "final_nodes": plant.ready_nodes,
        "machines_started": starts,
        "machines_stopped": stops,
        "mean_hpa_target": float(hpa.target),
    }


ARMS = ["hpa70_ca", "hpa50_ca", "omni_observe_hpa70_ca", "omni_target_hpa70_ca"]


def run(out: Path, mode: str = "both") -> dict:
    traces = load_all()
    rows = []
    for name, series in traces.items():
        for arm in ARMS:
            if mode in ("both", "open_loop"):
                cfg = HarnessConfig()
                cfg.hpa.target = 0.50 if "hpa50" in arm else 0.70
                rows.append(replay_open_loop(name, series, arm, cfg))
            if mode in ("both", "closed_loop"):
                cfg = HarnessConfig()
                cfg.plant.duration_s = 24 * 3600
                cfg.hpa.target = 0.50 if "hpa50" in arm else 0.70
                rows.append(replay_closed_loop(name, series, arm, cfg))
    means = {}
    for mode_n in sorted({r["mode"] for r in rows}):
        means[mode_n] = {}
        for arm in ARMS:
            sub = [r for r in rows if r["arm"] == arm and r["mode"] == mode_n]
            keys = [k for k in sub[0] if k not in ("trace", "arm", "mode") and isinstance(sub[0][k], (int, float))]
            means[mode_n][arm] = {k: float(np.mean([r[k] for r in sub])) for k in keys}
    obs = None
    open_rows = [r for r in rows if r["mode"] == "open_loop"]
    if open_rows:
        a = {(r["trace"]): r["energy_kwh"] for r in open_rows if r["arm"] == "hpa70_ca"}
        b = {(r["trace"]): r["energy_kwh"] for r in open_rows if r["arm"] == "omni_observe_hpa70_ca"}
        obs = int(sum(abs(a[k] - b[k]) < 1e-12 for k in a))
    summary = {
        "kind": "recorded_trace_replay",
        "source": "PlanetLab/CoMon 2011 CPU percent, 5-min samples, hold-last to 15s",
        "not": "live metrics-server; live kind cluster was not available in this environment",
        "traces": list(traces),
        "n_traces": len(traces),
        "arms": ARMS,
        "observe_energy_identical_open_loop": obs,
        "means": means,
        "rows": rows,
    }
    out.mkdir(parents=True, exist_ok=True)
    def _enc(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        raise TypeError(type(o))
    (out / "TRACE_REPLAY.json").write_text(json.dumps(summary, indent=2, default=_enc))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results"))
    ap.add_argument("--mode", default="both", choices=["open_loop", "closed_loop", "both"])
    a = ap.parse_args()
    s = run(Path(a.out), a.mode)
    print(json.dumps({
        "traces": s["n_traces"],
        "observe_identical": s["observe_energy_identical_open_loop"],
        "means": {m: {arm: {k: round(v, 4) for k, v in vals.items() if k in
                            ("energy_kwh", "availability", "scale_up_events",
                             "scale_down_events", "final_replicas", "mean_metric",
                             "machines_started")}
                      for arm, vals in arms.items()}
                  for m, arms in s["means"].items()},
    }, indent=2))


if __name__ == "__main__":
    main()
