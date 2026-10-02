# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Multi-workload fleet benchmark at 15-second resolution.

Baselines: HPA (targets 0.5, 0.7, 0.8) + Cluster Autoscaler; HPA 0.7 + Karpenter-lite; HPA 0.7 + Karpenter-lite + VPA-lite.
Omni-Compass arms (governor evaluated every 60 s on fleet telemetry; equation (2) push computed on the evolved state):
  omni_observe      governor computes, HPA 0.7 + Cluster Autoscaler act (must equal hpa70_ca)
  omni_target_ca    governor writes the HPA target (rho*); Cluster Autoscaler unchanged
  omni_full         single authority: HPA target, request sizing (workloads at minimum replicas only, so the HPA does
                    not compensate), provisioning, consolidation and node power caps
  omni_full_*       ablations: no_gate, no_dynamics, no_power, no_requests
Every omni_full action passes the fleet shield:
  F1 no consolidation while pods are pending or backlog exceeds shield_backlog of capacity
  F2 no consolidation of a node younger than 5 minutes, or whose pods do not fit on the remaining nodes
  F3 no power-cap tightening in an interval in which capacity is provisioned; caps in [cap_min, 1]
"""
from __future__ import annotations

import argparse, csv, hashlib, json, math, sys
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass.adapter import Governor, AllocationLaw, OBSERVE, AUTOPILOT
from k8s_fleet.plant import FleetConfig, Fleet, generate_workloads, TICK_S
from k8s_fleet.controllers import HPA, ClusterAutoscaler, Karpenter, RequestSizer, _fits_elsewhere, _pending_nodes

BASELINES = ["hpa70_ca", "hpa50_ca", "hpa80_ca", "hpa70_karpenter", "hpa70_karpenter_vpa"]
OMNI = ["omni_observe", "omni_target_ca", "omni_full", "omni_full_no_gate", "omni_full_no_dynamics", "omni_full_no_power",
        "omni_full_no_requests"]
ARMS = BASELINES + OMNI


@dataclass(frozen=True)
class OmniFleetLaw:
    period_ticks: int = 4
    target_lo: float = 0.55
    target_hi: float = 0.92
    req_q: float = 90.0
    req_margin: float = 0.15
    pack: float = 0.85
    consolidate_dwell_ticks: int = 8
    cap_margin: float = 0.20
    cap_min: float = 0.70
    shield_backlog: float = 0.01
    push_release: float = 0.01


def telemetry_obs(tel: Dict[str, float], site_limit_w: float, thermal: float) -> Dict[str, float]:
    cap = max(1e-9, tel["capacity"])
    return {"queue_ratio": min(2.0, tel["backlog"] / cap), "load_ratio": min(2.0, tel["demand"] / cap),
            "power_stress": tel["power_w"] / site_limit_w, "thermal": thermal, "network_stress": 0.0,
            "drift_ratio": 0.0, "security_block": 0.0, "stale": 0.0}


def simulate(seed: int, arm: str, cfg: FleetConfig, olaw: OmniFleetLaw, record: list = None) -> Dict:
    wls = generate_workloads(cfg, seed)
    f = Fleet(cfg, wls)
    site_limit = f.cfg.max_nodes * (cfg.node_vcpu * 1.2 + cfg.node_gib * 0.392) * cfg.pue * 0.5
    hpa = HPA(0.5 if arm == "hpa50_ca" else 0.8 if arm == "hpa80_ca" else 0.7)
    ca = ClusterAutoscaler() if arm in ("hpa70_ca", "hpa50_ca", "hpa80_ca", "omni_observe", "omni_target_ca") else None
    kp = Karpenter() if arm in ("hpa70_karpenter", "hpa70_karpenter_vpa") else None
    full = arm.startswith("omni_full")
    sizer = RequestSizer(q=olaw.req_q, margin=olaw.req_margin, only_at_min=True) if (arm == "hpa70_karpenter_vpa" or (full and arm != "omni_full_no_requests")) else None
    if arm == "hpa70_karpenter_vpa":
        sizer = RequestSizer()
    gov = None
    if arm.startswith("omni"):
        gov = Governor(law=AllocationLaw(push_release=olaw.push_release), evolve=arm != "omni_full_no_dynamics")
        gov.set_mode(OBSERVE if arm == "omni_observe" else AUTOPILOT)
    thermal = 0.3; last_prov = -10 ** 9; last_cons = -10 ** 9; converged = True; rho = 0.7
    healthy = 0; served_sum = demand_sum = 0.0; backlogs = []; nodes_hist = []; shield_blocks = 0; trace = []
    cap_travel = 0.0
    for tick in range(cfg.ticks):
        tel = f.step(tick)
        demand_sum += tel["demand"]; served_sum += min(tel["served"], tel["demand"] + 1e9)
        healthy += int(tel["worst_served"] >= cfg.healthy_served and tel["pending"] == 0)
        backlogs.append(tel["backlog"]); nodes_hist.append(tel["nodes"])
        thermal = 0.9 * thermal + 0.1 * min(1.5, tel["power_w"] / site_limit)
        if gov is not None and tick % olaw.period_ticks == 0:
            obs = telemetry_obs(tel, site_limit, thermal)
            gov.current_cap = float(np.mean([n.cap for n in f.nodes])) if f.nodes else 1.0
            gov.nodes = len(f.nodes)
            d = gov.step(obs, 0)
            rho = float(d["demand"])
            converged = arm == "omni_full_no_gate" or gov.last_push <= olaw.push_release
            if record is not None:
                record.append({"scenario_id": seed, "step": tick // olaw.period_ticks, "q": obs["queue_ratio"], "load": obs["load_ratio"],
                               "power": obs["power_stress"], "thermal": obs["thermal"], "network": 0.0, "drift": 0.0, "stale": 0.0,
                               "security": 0.0, "conflicts": 0, "current_cap": gov.current_cap, "nodes": gov.nodes, "_py": d})
        if arm in ("omni_target_ca",) or full:
            hpa.target = float(np.clip(rho, olaw.target_lo, olaw.target_hi))
        hpa.step(f, tick)
        if sizer is not None:
            sizer.step(f, tick, allow=(converged if full else True), hpa_target=(hpa.target if full else 0.0))
        if ca is not None:
            ca.step(f, tick)
        if kp is not None:
            kp.step(f, tick)
        if full:
            k = _pending_nodes(f, tick)
            if k > 0:
                f.add_nodes(k, tick, cfg.karpenter_boot_s); last_prov = tick
            elif tick % olaw.period_ticks == 0 and len(f.nodes) > cfg.min_nodes:
                ready = [n for n in f.nodes if n.ready_at <= tick]
                alloc = cfg.node_allocatable
                req_total = sum(f.requested(n) for n in f.nodes)
                want = converged and tick - max(last_prov, last_cons) >= olaw.consolidate_dwell_ticks and \
                    req_total <= (len(f.nodes) - 1) * alloc * olaw.pack
                if want:
                    cand = [n for n in sorted(ready, key=lambda n: f.requested(n))]
                    ok = f.pending == {} and tel["backlog"] <= olaw.shield_backlog * max(1e-9, tel["capacity"])
                    victim = next((n for n in cand if tick - n.added_at >= 300 // TICK_S and _fits_elsewhere(f, n, tick)), None)
                    if ok and victim is not None:
                        f.remove_node(victim); f.schedule(tick); last_cons = tick
                    else:
                        shield_blocks += 1
            if arm != "omni_full_no_power":
                use = getattr(f, "node_use", {})
                for n in f.nodes:
                    old = n.cap
                    if tel["backlog"] > olaw.shield_backlog * max(1e-9, tel["capacity"]) or last_prov == tick:
                        new = max(old, 1.0) if tel["backlog"] > olaw.shield_backlog * max(1e-9, tel["capacity"]) else old
                    else:
                        new = float(np.clip(use.get(id(n), 0.0) / cfg.node_vcpu * (1.0 + olaw.cap_margin), olaw.cap_min, 1.0))
                    cap_travel += abs(new - old); n.cap = new
        trace.append((len(f.nodes), sum(w.replicas for w in f.w.values()), round(f.energy_wh, 9)))
    return {"seed": seed, "arm": arm, "energy_kwh": f.energy_wh / 1000.0, "time_healthy": healthy / cfg.ticks,
            "served_fraction": min(1.0, served_sum / max(1e-9, demand_sum)), "backlog_p95": float(np.percentile(backlogs, 95)),
            "node_starts": f.starts, "node_stops": f.stops, "evictions": f.evictions,
            "request_changes": sizer.changes if sizer else 0, "mean_nodes": float(np.mean(nodes_hist)), "peak_nodes": max(nodes_hist),
            "power_cap_travel": cap_travel, "shield_blocks": shield_blocks,
            "trace_hash": hashlib.sha256(repr(trace).encode()).hexdigest()[:16]}


LOWER = ["energy_kwh", "backlog_p95", "node_starts", "node_stops", "evictions", "mean_nodes", "peak_nodes"]
HIGHER = ["time_healthy", "served_fraction"]


def paired(rows, base, cand, m, rng):
    A = {r["seed"]: r[m] for r in rows if r["arm"] == base}; B = {r["seed"]: r[m] for r in rows if r["arm"] == cand}
    d = np.array([B[k] - A[k] for k in sorted(A)])
    bs = d[rng.integers(0, len(d), (4000, len(d)))].mean(axis=1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {"metric": m, "mean_delta": float(d.mean()), "ci95": [float(lo), float(hi)]}


def run(scenarios: int, seed0: int, out: Path, cfg: FleetConfig = FleetConfig(), olaw: OmniFleetLaw = OmniFleetLaw(), arms=ARMS):
    rows = [simulate(seed0 + i, a, cfg, olaw) for i in range(scenarios) for a in arms]
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "RUNS.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    rng = np.random.default_rng(12345)
    means = {a: {m: float(np.mean([r[m] for r in rows if r["arm"] == a])) for m in LOWER + HIGHER + ["request_changes", "power_cap_travel", "shield_blocks"]} for a in arms}
    comps = {}
    for base in ("hpa70_ca", "hpa70_karpenter", "hpa70_karpenter_vpa"):
        for cand in ("omni_target_ca", "omni_full"):
            if base in arms and cand in arms:
                comps[f"{cand}_vs_{base}"] = [paired(rows, base, cand, m, rng) for m in LOWER + HIGHER]
    for abl in ("omni_full_no_gate", "omni_full_no_dynamics", "omni_full_no_power", "omni_full_no_requests"):
        if abl in arms:
            comps[f"omni_full_vs_{abl}"] = [paired(rows, abl, "omni_full", m, rng) for m in LOWER + HIGHER]
    ident = None
    if "omni_observe" in arms:
        a = {r["seed"]: r["trace_hash"] for r in rows if r["arm"] == "hpa70_ca"}
        b = {r["seed"]: r["trace_hash"] for r in rows if r["arm"] == "omni_observe"}
        ident = sum(a[k] == b[k] for k in a)
    summ = {"scenarios": scenarios, "seed0": seed0, "config": asdict(cfg), "omni_fleet_law": asdict(olaw), "means": means,
            "paired": comps, "observe_identical_to_hpa70_ca": ident}
    (out / "SUMMARY.json").write_text(json.dumps(summ, indent=2))
    return summ


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--scenarios", type=int, default=100); ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--cap-exponent", type=float, default=2.0)
    a = ap.parse_args()
    s = run(a.scenarios, a.seed, Path(a.out), FleetConfig(cap_exponent=a.cap_exponent))
    for arm, m in s["means"].items():
        print(arm.ljust(24), {k: round(v, 3) for k, v in m.items() if k in ("energy_kwh", "time_healthy", "served_fraction", "node_starts", "node_stops", "mean_nodes")})
    print("observe identical:", s["observe_identical_to_hpa70_ca"], "/", s["scenarios"])


if __name__ == "__main__":
    main()
