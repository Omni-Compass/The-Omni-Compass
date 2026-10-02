# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""15-second control-plane benchmark: HPA + CA/Karpenter ± Omni-Compass."""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from .cluster_autoscaler import ClusterAutoscaler
from .config import HarnessConfig
from .hpa import HorizontalPodAutoscaler
from .karpenter import KarpenterLite
from .metrics_server import MetricsServer
from .omni_bridge import OmniLoop
from .plant import Plant
from .scenarios import Scenario, generate, source

ARMS = [
    "hpa70_ca",
    "hpa50_ca",
    "hpa80_ca",
    "hpa70_karpenter",
    "omni_observe_hpa70_ca",
    "omni_target_hpa70_ca",
    "omni_target_down_hpa70_ca",
    "omni_target_gate_hpa70_ca",
    "omni_protect_full",
    "omni_throughput_full",
]

BASELINES = {"hpa70_ca", "hpa50_ca", "hpa80_ca", "hpa70_karpenter"}


def _hpa_target(arm: str) -> float:
    if "hpa50" in arm:
        return 0.50
    if "hpa80" in arm:
        return 0.80
    return 0.70


def simulate(scn: Scenario, arm: str, cfg: HarnessConfig) -> Dict[str, Any]:
    cfg = deepcopy(cfg)
    cfg.seed = scn.seed
    cfg.scenario_id = scn.scenario_id
    cfg.family = scn.family
    cfg.hpa.target = _hpa_target(arm)
    rng = np.random.default_rng(scn.seed)
    plant = Plant.new(cfg)
    ms = MetricsServer(cfg.metrics, rng)
    ms.cfg.drop_probability = scn.metrics_drop
    hpa = HorizontalPodAutoscaler(cfg.hpa)
    ca = ClusterAutoscaler(cfg.ca)
    karp = KarpenterLite(cfg.karpenter) if "karpenter" in arm else None
    omni = OmniLoop(arm, cfg) if arm.startswith("omni_") else None
    if omni and "down" in arm:
        ca.allow_scale_down = False
    if omni and ("full" in arm or "protect" in arm or "throughput" in arm):
        ca.allow_scale_down = False
    if cfg.pool == "always_on":
        ca.allow_scale_down = False

    dt = cfg.plant.dt_s
    steps = cfg.plant.duration_s // dt
    energy = 0.0
    work = 0.0
    demand = 0.0
    peak = 0.0
    v_q = v_p = v_h = healthy = 0
    recovered = False
    rec_pending = False
    rec_t = None
    rec_done_s = None
    streak = 0
    starts = stops = 0
    rev = 0
    last_nd = 0
    contra = 0
    pages = 0
    trace = []
    q_hist = []

    for i in range(steps):
        now = i * dt
        src = source(scn, now)
        snap = plant.tick(now, src)
        demand += snap["demand_cores"] * (dt / 60.0)
        work += snap["delivered_cores"] * (dt / 60.0)
        energy += snap["power_kw"] * (dt / 3600.0)
        peak = max(peak, snap["power_kw"])
        q_hist.append(snap["queue"])

        ms.observe(now, snap["true_hpa_metric"], snap["ready_replicas"])
        metric = ms.cpu_average_utilization(now)

        d = None
        if omni is not None:
            d = omni.maybe_step(now, snap, plant.power_cap, plant.ready_nodes)
            if omni.writes and d is not None:
                if "target" in arm or "gate" in arm or "full" in arm or "protect" in arm or "throughput" in arm or "observe" not in arm:
                    hpa.target = float(d["demand"])
                if "gate" in arm:
                    released = (
                        abs(omni.gov.last_push) <= max(0.02, 4.0 * omni.gov.law.push_release)
                        and snap["queue_ratio"] < 0.12
                        and snap["pending_pods"] == 0
                    )
                    above_floor = plant.ready_nodes > cfg.plant.initial_nodes
                    ca.unneeded_need = cfg.gate_unneeded_s if (released and above_floor) else cfg.ca.unneeded_s
                    ca.delay_add_need = cfg.ca.delay_after_add_s

        new_rep = hpa.step(now, plant.running_replicas, metric)
        plant.set_replicas(new_rep, now)

        node_delta = 0
        if karp is not None:
            node_delta = karp.step(
                now, plant.ready_nodes, plant.booting, snap["pending_pods"],
                snap["request_util"], plant.running_replicas, plant.pods_per_node, dt,
            )
        else:
            node_delta = ca.step(
                now, plant.ready_nodes, plant.booting, snap["pending_pods"],
                snap["request_util"], dt,
            )

        if omni is not None and omni.writes and d is not None and omni.fresh:
            acts = []
            if ("down" in arm or "full" in arm or "protect" in arm or "throughput" in arm) and int(d["node_delta"]) != 0:
                tgt = plant.ready_nodes + int(d["node_delta"])
                acts.append({"manager": "Omni", "action": "nodes", "target": tgt,
                             "direction": 1 if d["node_delta"] > 0 else -1})
            if ("full" in arm or "protect" in arm or "throughput" in arm):
                acts.append({"manager": "Omni", "action": "power_cap", "target": float(d["power_cap"]),
                             "direction": -1 if d["power_cap"] < plant.power_cap else 1})
            acts = omni.apply_shield(acts, snap, plant.ready_nodes, plant.power_cap)
            can_down = (
                snap["pending_pods"] == 0
                and snap["request_util"] < cfg.ca.utilization_threshold
                and snap["queue_ratio"] < 0.28
                and ca.since_add_s >= cfg.ca.delay_after_add_s
            )
            for a in acts:
                if a["action"] == "nodes":
                    raw = a["target"] - plant.ready_nodes
                    if a["direction"] < 0 and can_down:
                        node_delta = min(node_delta, max(-cfg.ca.max_delete_per_scan, raw))
                    elif a["direction"] > 0 and ("full" in arm or "protect" in arm or "throughput" in arm):
                        node_delta = max(node_delta, min(cfg.ca.max_add_per_scan, raw))
                elif a["action"] == "power_cap":
                    plant.power_cap = max(0.65, min(1.0, float(a["target"])))

        before = plant.total_nodes
        ready_s = cfg.karpenter.node_ready_s if karp is not None else cfg.ca.node_ready_s
        plant.schedule_nodes(plant.total_nodes + node_delta, now, ready_s)
        nd = 1 if plant.total_nodes > before else -1 if plant.total_nodes < before else 0
        starts += max(0, plant.total_nodes - before)
        stops += max(0, before - plant.total_nodes)
        if nd and last_nd and nd != last_nd:
            rev += 1
        if nd:
            last_nd = nd

        v_q += int(snap["queue_ratio"] > 0.35)
        v_p += int(snap["power_stress"] > 1.05)
        v_h += int(snap["thermal"] > 1.03)
        ok = snap["queue_ratio"] < 0.28 and snap["power_stress"] <= 1.02 and snap["thermal"] < 0.96
        healthy += int(ok)
        streak = streak + 1 if ok else 0
        if src["event"]:
            rec_pending = True
            rec_t = scn.event_start_s + scn.event_duration_s
        elif rec_pending and rec_t is not None and now >= rec_t and streak >= 4:
            recovered = True
            rec_pending = False
            rec_done_s = now
        if snap["queue_ratio"] > 0.35:
            pages += 1

        trace.append((
            round(snap["queue_ratio"], 6),
            round(snap["power_kw"], 4),
            plant.ready_nodes,
            plant.desired_replicas,
            round(plant.power_cap, 4),
            round(hpa.target, 4),
        ))

    n = max(1, steps)
    if recovered and rec_done_s is not None and rec_t is not None:
        rec_min = max(0.0, (rec_done_s - rec_t) / 60.0)
    else:
        rec_min = cfg.plant.duration_s / 60.0
    return {
        "scenario_id": scn.scenario_id,
        "family": scn.family,
        "pool": cfg.pool,
        "arm": arm,
        "availability": work / max(1e-9, demand),
        "energy_kwh": energy,
        "peak_power_kw": peak,
        "time_healthy": healthy / n,
        "violation_backlog": v_q / n,
        "violation_power": v_p / n,
        "violation_heat": v_h / n,
        "sla_physical": (v_q + v_p + v_h) / n / 3.0,
        "recovered": int(recovered),
        "recovery_minutes": rec_min if recovered else cfg.plant.duration_s / 60.0,
        "machines_started": starts,
        "machines_stopped": stops,
        "scale_reversals": rev,
        "pages": pages,
        "mean_queue": float(np.mean(q_hist)) if q_hist else 0.0,
        "final_nodes": plant.ready_nodes,
        "final_replicas": plant.desired_replicas,
        "invariant_violations": float(omni.inv if omni else 0),
        "invariant_violations_ex_power": float(omni.inv_ex if omni else 0),
        "shield_hits": int(omni.shield_hits if omni else 0),
        "contradictions": contra,
        "trace_hash": hashlib.sha256(repr(trace).encode()).hexdigest()[:16],
    }


def run(scenarios: int, seed: int, out: Path, arms: List[str] = None) -> Dict[str, Any]:
    arms = list(arms or ARMS)
    cfg = HarnessConfig(seed=seed)
    scns = generate(scenarios, seed, cfg.plant.duration_s)
    rows = [simulate(s, a, cfg) for s in scns for a in arms]
    out.mkdir(parents=True, exist_ok=True)
    means = {}
    for a in arms:
        sub = [r for r in rows if r["arm"] == a]
        keys = [k for k in sub[0] if k not in ("scenario_id", "family", "arm", "trace_hash")
                and isinstance(sub[0][k], (int, float)) and not isinstance(sub[0][k], bool)]
        means[a] = {k: float(np.mean([r[k] for r in sub])) for k in keys}
    obs_match = None
    if "omni_observe_hpa70_ca" in arms and "hpa70_ca" in arms:
        a = {r["scenario_id"]: r["trace_hash"] for r in rows if r["arm"] == "hpa70_ca"}
        b = {r["scenario_id"]: r["trace_hash"] for r in rows if r["arm"] == "omni_observe_hpa70_ca"}
        obs_match = sum(a[i] == b[i] for i in a)
    summary = {
        "kind": "k8s_controlplane_replica",
        "disclaimer": "Algorithm replica of documented HPA/CA/metrics-server behaviour; not upstream binaries.",
        "scenarios": len(scns),
        "steps": cfg.plant.duration_s // cfg.plant.dt_s,
        "dt_s": cfg.plant.dt_s,
        "duration_s": cfg.plant.duration_s,
        "omni_period_s": cfg.omni_period_s,
        "seed": seed,
        "arms": arms,
        "hpa_defaults": asdict(cfg.hpa),
        "ca_defaults": asdict(cfg.ca),
        "means": means,
        "observe_identical_to_hpa70_ca": obs_match,
        "rows": rows,
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=24)
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--out", default="k8s_controlplane/results")
    a = ap.parse_args()
    s = run(a.scenarios, a.seed, Path(a.out))
    print(json.dumps({k: {m: round(v, 4) for m, v in s["means"][k].items()
                          if m in ("energy_kwh", "time_healthy", "availability",
                                   "violation_backlog", "violation_power",
                                   "recovery_minutes", "recovered",
                                   "machines_started", "machines_stopped")}
                      for k in s["arms"]}, indent=2))
    print("observe identical:", s["observe_identical_to_hpa70_ca"], "/", s["scenarios"])


if __name__ == "__main__":
    main()
