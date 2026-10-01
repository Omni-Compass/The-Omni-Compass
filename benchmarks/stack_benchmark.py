"""Stack governance benchmark.

Arms:
  native            each manager executes its own proposal; a paged human intervenes after the operator delay
  omni_observe      governor in OBSERVE
  omni_autopilot    governor in AUTOPILOT
  omni_no_dynamics  AUTOPILOT with equations (1)-(7) not evolved
  omni_kill         AUTOPILOT, killed at event onset + 2 intervals
  omni_switch_on    OBSERVE until event onset, then AUTOPILOT
"""
from __future__ import annotations

import argparse, csv, hashlib, json, math, sys, time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass import stack_sim as S
from omnicompass.shield import enforce, violations, ShieldLimits
from omnicompass.adapter import mode_law
from omnicompass.adapter import (Governor, AllocationLaw, OBSERVE, AUTOPILOT, directive_to_actions,
                                 observe_vector, assimilate)

ARMS = ["native", "k8s_ref_50", "k8s_ref_60", "k8s_ref_70", "k8s_ref_80", "omni_k8s_protect", "omni_k8s_throughput",
        "omni_k8s_observe", "omni_k8s_kill", "omni_k8s_throughput_no_dynamics", "omni_k8s_throughput_no_gate",
        "omni_observe", "omni_pipeline", "omni_direct", "omni_direct_no_dynamics",
        "omni_direct_no_shield", "omni_kill", "omni_switch_on"]
K8S_REFS = ("k8s_ref_50", "k8s_ref_60", "k8s_ref_70", "k8s_ref_80")
LAYERED = {"omni_k8s_protect", "omni_k8s_throughput", "omni_k8s_observe", "omni_k8s_kill", "omni_k8s_throughput_no_dynamics",
           "omni_k8s_throughput_no_gate"}
THROUGHPUT = {"omni_k8s_throughput", "omni_k8s_throughput_no_dynamics", "omni_k8s_throughput_no_gate"}
BASELINES = ("native",) + K8S_REFS
DIRECT_SENSING = {*K8S_REFS, *LAYERED, "omni_direct", "omni_direct_no_dynamics", "omni_direct_no_shield", "omni_kill",
                  "omni_switch_on"}
DIRECT_ACTUATION = {*LAYERED, "omni_direct", "omni_direct_no_dynamics", "omni_direct_no_shield", "omni_kill", "omni_switch_on"}
SHIELDED = {*LAYERED, "omni_pipeline", "omni_direct", "omni_direct_no_dynamics", "omni_kill", "omni_switch_on"}


class K8sReference:
    """Documented-behaviour reference model of Kubernetes autoscaling (not the upstream controllers).

    HPA (kubernetes.io, Horizontal Pod Autoscaling): desired = ceil(current * metric / target); no change while
      |metric/target - 1| <= 0.1; scale-down uses the highest recommendation over the 300 s stabilization window.
      metric = load ratio; the target is workload configuration, so the benchmark runs targets 0.5, 0.6, 0.7, 0.8.
    Cluster Autoscaler (kubernetes/autoscaler FAQ), simplified: scale-up when work is unschedulable (backlog present),
      sized to the pending work, without scheduling-feasibility simulation; a node is removed after it has been unneeded (utilization < 0.5) for 10 minutes, not within
      10 minutes of a scale-up.
    Alerting: page when queue ratio > 0.35 for 15 minutes (Prometheus 'for: 15m' rule).
    Terraform is not a live capacity controller (desired size ignored after creation).
    Power/thermal, rollout, rollback and routing proposals are executed as proposed.
    Not represented: Karpenter consolidation, VPA, pod scheduling constraints, disruption budgets.
    """

    def __init__(self, hpa_target: float):
        self.hpa_target = hpa_target
        self.rec_hist = []
        self.under = 0
        self.since_add = 99
        self.alert = 0

    def actions(self, props, st, obs, cfg):
        acts = []
        load = float(obs.get("load_ratio", 0.0)); q = float(obs.get("queue_ratio", 0.0))
        ratio = load / self.hpa_target
        cur = int(st["replicas"])
        rec = cur if abs(ratio - 1.0) <= 0.1 else max(20, min(500, int(np.ceil(cur * ratio))))
        self.rec_hist = (self.rec_hist + [rec])[-2:]
        want = rec if rec >= cur else max(self.rec_hist)
        if want != cur:
            acts.append({"manager": "HPA", "action": "replicas", "target": want, "direction": 1 if want > cur else -1})
        n = int(st["actual_nodes"])
        util = min(1.0, load)
        self.since_add += 1
        if q > 0.0:
            need = int(np.ceil(q * n))
            if need > 0 and n < cfg.maximum_nodes:
                acts.append({"manager": "Cluster Autoscaler", "action": "nodes", "target": min(cfg.maximum_nodes, n + need), "direction": 1})
                self.since_add = 0
            self.under = 0
        else:
            self.under = self.under + 1 if util < 0.5 else 0
            if self.under >= 2 and self.since_add >= 2 and n > cfg.minimum_nodes:
                acts.append({"manager": "Cluster Autoscaler", "action": "nodes", "target": n - 1, "direction": -1})
                self.under = 0
        for p in native_actions(props):
            if p["action"] in ("power_cap", "rollback", "route_shift", "rollout"):
                acts.append(p)
        if any(p["action"] == "alert" for p in props):
            acts.append({"manager": "Alertmanager", "action": "alert", "target": 1, "direction": 1})
        self.alert = self.alert + 1 if q > 0.35 else 0
        if self.alert >= 3:
            acts.append({"manager": "Alertmanager", "action": "page", "target": 1, "direction": 1})
            self.alert = 0
        return acts
clamp = S._mom_clamp


def native_actions(proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Native stack actions."""
    acts = [p for k in ("replicas", "nodes", "terraform_plan", "rollout") for p in proposals if p["action"] == k]
    if any(p["action"] == "rollback" for p in proposals):
        acts.append({"manager": "Argo CD / Rollouts", "action": "rollback", "target": 1.0, "direction": -1})
    caps = [float(p["target"]) for p in proposals if p["action"] == "power_cap"]
    if caps:
        acts.append({"manager": "Power/Thermal", "action": "power_cap", "target": min(caps), "direction": -1})
    if any(p["action"] == "route_shift" for p in proposals):
        acts.append({"manager": "Istio/Cilium", "action": "route_shift", "target": 1.0, "direction": 1})
    acts += [p for p in proposals if p["action"] == "alert"] + [p for p in proposals if p["action"] == "page"]
    return acts


def layer_over_k8s(omni_acts, d, k8s, props, st, obs, cfg):
    """Omni-Compass governing Kubernetes: Kubernetes autoscalers run as the execution layer; the governor sets the
    HPA target (rho*), keeps Cluster Autoscaler scale-up, owns scale-down, power caps, rollback and routing."""
    k8s.hpa_target = float(d["demand"])
    k_acts = k8s.actions(props, st, obs, cfg)
    n = int(st["actual_nodes"])
    k_up = max([int(a["target"]) for a in k_acts if a["action"] == "nodes" and a["direction"] > 0], default=n)
    o_nodes = [a for a in omni_acts if a["action"] == "nodes"]
    o_tgt = int(o_nodes[0]["target"]) if o_nodes else n
    tgt = max(k_up, o_tgt) if (k_up > n or o_tgt > n) else o_tgt
    out = [a for a in omni_acts if a["action"] not in ("nodes", "replicas")]
    if tgt != n:
        out.append({"manager": "Omni-Compass/Kubernetes", "action": "nodes", "target": tgt, "direction": 1 if tgt > n else -1})
    for a in k_acts:
        if a["action"] == "replicas" and (a["direction"] > 0 or tgt < n):
            out.append(a)
    if any(a["direction"] > 0 and a["action"] in ("nodes", "replicas") for a in out):
        out = [a for a in out if not (a["action"] == "power_cap" and float(a["target"]) < float(st["power_cap"]) - 1e-9)]
    return out


def contradictions(actions, state, security_denied) -> int:
    c = 0
    nd = [a["direction"] for a in actions if a["action"] in ("nodes", "terraform_plan")]
    if nd and min(nd) < 0 < max(nd):
        c += 1
    rd = [a["direction"] for a in actions if a["action"] == "replicas"]
    if rd and min(rd) < 0 < max(rd):
        c += 1
    kinds = {a["action"] for a in actions}
    if "rollout" in kinds and "rollback" in kinds:
        c += 1
    up = any(a["direction"] > 0 and a["action"] in ("nodes", "terraform_plan", "replicas", "rollout") for a in actions)
    tighten = any(a["action"] == "power_cap" and float(a["target"]) < float(state["power_cap"]) - 1e-9 for a in actions)
    if up and tighten:
        c += 1
    if security_denied and any(a["direction"] > 0 and a["action"] in ("nodes", "terraform_plan", "rollout") for a in actions):
        c += 1
    if sum(1 for a in actions if a["action"] == "alert") > 1:
        c += 1
    return c


def simulate(scn, arm: str, cfg, law: AllocationLaw) -> Dict[str, Any]:
    st = {"actual_nodes": cfg.initial_nodes, "available_nodes": cfg.initial_nodes,
          "terraform_desired_nodes": cfg.initial_nodes, "replicas": 100, "pending_queue": 0.0, "thermal": 0.32,
          "smoothed_load": scn.base_load_fraction, "power_cap": 1.0, "network_recovery": 0.0,
          "terraform_pending_target": None, "terraform_apply_step": None, "last_node_direction": 0,
          "last_replica_direction": 0, "operator_page_step": None, "operator_ack_step": None}
    gov = None
    if arm in THROUGHPUT:
        law = mode_law("throughput", law)
    if arm == "omni_k8s_throughput_no_gate":
        from dataclasses import replace as _replace
        law = _replace(law, push_release=9.0)
    shield_lim = ShieldLimits(power_limit=1e9) if arm in THROUGHPUT else ShieldLimits()
    k8s = K8sReference(int(arm[-2:]) / 100.0) if arm in K8S_REFS else (K8sReference(0.7) if arm in LAYERED else None)
    shield_hits = inv_viol = inv_viol_ex_power = 0
    node_travel = cap_travel = thermal_travel = 0.0
    node_starts = node_stops = 0
    if arm not in BASELINES:
        gov = Governor(law=law, evolve=not arm.endswith("_no_dynamics"))
        gov.set_mode(OBSERVE if arm in ("omni_observe", "omni_switch_on", "omni_k8s_observe") else AUTOPILOT)
    hist, qv, rec = [], [], []
    dem = done = energy = nh = unn = peak = 0.0
    sla_p = sla_c = adm_n = contra = rev = secv = pages = manual = nact = 0
    v_queue = v_power = v_heat = 0
    rec_pending, rec_start, streak = False, None, 0
    authority_steps = 0
    trace = []
    for step in range(cfg.steps):
        if arm in ("omni_kill", "omni_k8s_kill") and step == scn.event_start + 2:
            gov.kill()
        if arm == "omni_switch_on" and step == scn.event_start:
            gov.set_mode(AUTOPILOT)
        rng = np.random.default_rng(scn.seed + step * 7919 + 101)
        src = S._mom_source_signals(scn, step, cfg, rng)
        if st["terraform_apply_step"] is not None and step >= st["terraform_apply_step"]:
            st["actual_nodes"] = st["terraform_desired_nodes"] = int(st["terraform_pending_target"])
            st["terraform_pending_target"] = st["terraform_apply_step"] = None
        failed = int(round(cfg.initial_nodes * src["failed_fraction"]))
        st["available_nodes"] = max(cfg.minimum_nodes, st["actual_nodes"] - failed)
        demand = (src["demand_fraction"] + src["batch_fraction"]) * cfg.initial_nodes * cfg.capacity_units_per_node * src["rollout_multiplier"]
        dem += demand
        st["pending_queue"] += demand
        eff_net = clamp(src["network_efficiency"] + st["network_recovery"], 0.45, 1.0)
        throttle = clamp(1.0 - max(0.0, st["thermal"] - 0.82) * 0.65, 0.58, 1.0)
        cap = st["available_nodes"] * cfg.capacity_units_per_node * eff_net * throttle * st["power_cap"]
        cap *= clamp(st["replicas"] / 100.0, 0.55, 1.35)
        work = min(st["pending_queue"], max(0.0, cap))
        st["pending_queue"] -= work
        done += work
        util = clamp(work / max(1.0, st["available_nodes"] * cfg.capacity_units_per_node), 0.0, 1.25)
        pkw = st["actual_nodes"] * (cfg.node_idle_kw + cfg.node_dynamic_kw * min(1.0, util)) * cfg.pue * st["power_cap"]
        pstress = pkw / max(1e-9, cfg.site_power_limit_kw * src["power_derate"])
        st["thermal"] = clamp(0.86 * st["thermal"] + 0.14 * (0.34 + 0.62 * min(1.35, pstress)), 0.0, 1.35)
        qratio = clamp(st["pending_queue"] / max(1.0, cap * 2.0), 0.0, 2.0)
        lratio = clamp(demand / max(1.0, cap), 0.0, 2.0)
        st["smoothed_load"] = 0.78 * st["smoothed_load"] + 0.22 * lratio
        drift = abs(st["terraform_desired_nodes"] - st["actual_nodes"]) / max(1.0, cfg.maximum_nodes - cfg.minimum_nodes)
        hist.append({"queue_ratio": qratio, "load_ratio": lratio, "thermal": st["thermal"], "power_stress": pstress,
                     "network_stress": clamp(1 - eff_net, 0, 1), "drift_ratio": drift,
                     "batch_fraction": src["batch_fraction"], "security_block": src["security_block"],
                     "rollout_multiplier": src["rollout_multiplier"], "stale": 0.0})
        if arm in DIRECT_SENSING:
            obs = S._mom_delayed_observation(hist, 0)
        else:
            delay = scn.telemetry_delay_steps + scn.kafka_lag_steps
            obs = S._mom_delayed_observation(hist, delay)
            if delay > 0:
                obs["stale"] = 1.0
            if src.get("telemetry_drop", 0.0) > 0.5:
                obs = S._mom_delayed_observation(hist, delay + 2)
                obs["stale"] = 1.0
        props = S._mom_proposals(st, obs, scn, step, cfg, src)
        nconf, _ = S._mom_conflict_count(props)
        denied = any(p["action"] == "deny_change" for p in props)
        if gov is not None:
            gov.current_cap = st["power_cap"]
            gov.nodes = st["actual_nodes"]
            d = gov.step(obs, nconf)
            if gov.has_authority:
                acts = directive_to_actions(d, st, props, cfg, direct_actuation=arm in DIRECT_ACTUATION)
                if arm in LAYERED:
                    acts = layer_over_k8s(acts, d, k8s, props, st, obs, cfg)
                if arm in SHIELDED:
                    acts, h = enforce(acts, st, obs, cfg, shield_lim)
                    shield_hits += h
                authority_steps += 1
            elif arm in LAYERED:
                k8s.hpa_target = 0.70
                acts = k8s.actions(props, st, obs, cfg)
            else:
                acts = native_actions(props)
        elif k8s is not None:
            acts = k8s.actions(props, st, obs, cfg)
        else:
            acts = native_actions(props)
        vv = violations(acts, st, hist[-1], cfg)
        inv_viol += len(vv)
        inv_viol_ex_power += sum(1 for v in vv if v != "I4")
        n_before, cap_before = st["actual_nodes"], st["power_cap"]
        c_step = contradictions(acts, st, denied)
        contra += c_step
        nact += len(acts)
        nd = rd = pg = 0
        st["network_recovery"] *= 0.55
        for a in acts:
            k = a["action"]
            if k == "replicas":
                t = int(a["target"]); rd = 1 if t > st["replicas"] else -1 if t < st["replicas"] else 0
                st["replicas"] = max(20, min(500, t))
            elif k == "nodes":
                t = max(cfg.minimum_nodes, min(cfg.maximum_nodes, int(a["target"])))
                nd = 1 if t > st["actual_nodes"] else -1 if t < st["actual_nodes"] else 0
                st["actual_nodes"] += int(np.sign(t - st["actual_nodes"])) * min(2, abs(t - st["actual_nodes"]))
            elif k == "terraform_plan":
                st["terraform_pending_target"] = max(cfg.minimum_nodes, min(cfg.maximum_nodes, int(a["target"])))
                st["terraform_apply_step"] = step + cfg.terraform_apply_delay_steps
            elif k == "power_cap":
                st["power_cap"] = clamp(float(a["target"]), 0.65, 1.0)
            elif k == "route_shift":
                st["network_recovery"] = max(st["network_recovery"], 0.16)
            elif k == "rollback":
                st["replicas"] = max(60, int(round(st["replicas"] * 0.88)))
            elif k == "page":
                pg += 1
        pages += pg
        node_travel += abs(st["actual_nodes"] - n_before)
        node_starts += max(0, st["actual_nodes"] - n_before)
        node_stops += max(0, n_before - st["actual_nodes"])
        cap_travel += abs(st["power_cap"] - cap_before)
        if len(hist) > 1:
            thermal_travel += abs(hist[-1]["thermal"] - hist[-2]["thermal"])
        if pg and st["operator_page_step"] is None:
            st["operator_page_step"] = step
            st["operator_ack_step"] = step + scn.operator_delay_steps
        if st["operator_ack_step"] is not None and step >= st["operator_ack_step"]:
            manual += 1
            st["operator_page_step"] = st["operator_ack_step"] = None
            st["power_cap"] = max(st["power_cap"], 0.90)
            st["actual_nodes"] = min(cfg.maximum_nodes, st["actual_nodes"] + 1)
        if nd and st["last_node_direction"] and nd != st["last_node_direction"]:
            rev += 1
        if rd and st["last_replica_direction"] and rd != st["last_replica_direction"]:
            rev += 1
        if nd: st["last_node_direction"] = nd
        if rd: st["last_replica_direction"] = rd
        if src["security_block"] > 0.5 and any(a["action"] in ("nodes", "terraform_plan", "rollout") and a["direction"] > 0 for a in acts):
            secv += 1
        req = max(cfg.minimum_nodes, min(cfg.maximum_nodes, int(math.ceil((demand + st["pending_queue"] * 0.45) / cfg.capacity_units_per_node))))
        unn += max(0, st["actual_nodes"] - req) * cfg.dt_hours
        nh += st["actual_nodes"] * cfg.dt_hours
        energy += pkw * cfg.dt_hours
        peak = max(peak, pkw)
        qv.append(st["pending_queue"])
        v_queue += int(qratio > 0.35); v_power += int(pstress > 1.05); v_heat += int(st["thermal"] > 1.03)
        phys = qratio > 0.35 or pstress > 1.05 or st["thermal"] > 1.03
        sla_p += int(phys)
        sla_c += int(phys or c_step > 0)
        adm = qratio < 0.28 and pstress <= 1.02 and st["thermal"] < 0.96 and c_step == 0
        adm_n += int(adm)
        streak = streak + 1 if adm else 0
        if S._mom_event_active(scn, step):
            rec_pending, rec_start = True, scn.event_start + scn.event_duration
        elif rec_pending and rec_start is not None and step >= rec_start and streak >= cfg.certification_streak:
            rec.append((step - rec_start + 1) * cfg.interval_minutes); rec_pending = False
        trace.append((round(qratio, 12), round(pkw, 12), st["actual_nodes"], st["replicas"], round(st["power_cap"], 12)))
    n = cfg.steps
    return {"scenario_id": scn.scenario_id, "family": scn.family, "arm": arm,
            "availability": done / max(1e-9, dem), "sla_violation_physical": sla_p / n,
            "sla_violation_total": sla_c / n, "violation_backlog": v_queue / n, "violation_power": v_power / n,
            "violation_heat": v_heat / n, "time_healthy": adm_n / n,
            "mean_queue": float(np.mean(qv)), "p95_queue": float(np.percentile(qv, 95)),
            "recovery_minutes": float(np.mean(rec)) if rec else n * cfg.interval_minutes, "recovered": int(bool(rec)),
            "energy_kwh": energy, "peak_power_kw": peak, "node_hours": nh, "idle_node_hours": unn,
            "contradictions": contra, "scale_reversals": rev, "security_violations": secv, "pages": pages,
            "human_interventions": manual, "actions": nact, "omni_authority_steps": authority_steps,
            "node_start_stop": node_travel, "machines_started": node_starts, "machines_stopped": node_stops,
            "machine_round_trips": (node_starts + node_stops - abs(st["actual_nodes"] - cfg.initial_nodes)) / 2.0, "power_cap_travel": cap_travel, "thermal_travel": thermal_travel,
            "invariant_violations": inv_viol, "invariant_violations_ex_power": inv_viol_ex_power,
            "shield_interventions": shield_hits,
            "trace_hash": hashlib.sha256(repr(trace).encode()).hexdigest()[:16]}


LOWER = ["machine_round_trips", "scale_reversals", "node_start_stop", "power_cap_travel", "thermal_travel", "invariant_violations", "invariant_violations_ex_power", "sla_violation_physical", "sla_violation_total", "violation_backlog", "violation_power", "violation_heat", "mean_queue", "p95_queue", "recovery_minutes", "energy_kwh",
         "peak_power_kw", "node_hours", "idle_node_hours", "contradictions", "scale_reversals", "security_violations",
         "pages", "human_interventions"]
HIGHER = ["availability", "time_healthy", "recovered"]
NEUTRAL = ["machines_started", "machines_stopped"]


def paired(rows, base, cand, metric, rng):
    A = {r["scenario_id"]: r[metric] for r in rows if r["arm"] == base}
    B = {r["scenario_id"]: r[metric] for r in rows if r["arm"] == cand}
    ids = sorted(A)
    d = np.array([B[i] - A[i] for i in ids], float)
    boots = d[rng.integers(0, len(d), (4000, len(d)))].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    good = d < 0 if metric in LOWER else d > 0
    bad = d > 0 if metric in LOWER else d < 0
    return {"metric": metric, "base_mean": float(np.mean([A[i] for i in ids])), "cand_mean": float(np.mean([B[i] for i in ids])),
            "mean_delta": float(d.mean()), "ci95": [float(lo), float(hi)], "better": int(good.sum()),
            "worse": int(bad.sum()), "tied": int(len(d) - good.sum() - bad.sum()), "n": len(d)}


def run(scenarios: int, seed: int, out: Path, law: AllocationLaw, arms=ARMS) -> Dict[str, Any]:
    cfg = S.ManagerBenchmarkConfig(profile="full", scenarios=scenarios, steps=72)
    scns = S._mom_generate_scenarios(cfg, seed)[:scenarios]
    rows = [simulate(s, a, cfg, law) for s in scns for a in arms]
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "RUNS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    rng = np.random.default_rng(12345)
    means = {a: {m: float(np.mean([r[m] for r in rows if r["arm"] == a])) for m in HIGHER + LOWER + NEUTRAL} for a in arms}
    comps = {}
    for base in [b for b in BASELINES if b in arms]:
        for cand in [a for a in arms if a not in BASELINES]:
            comps[f"{cand}_vs_{base}"] = [paired(rows, base, cand, m, rng) for m in HIGHER + LOWER]
    for x, y in (("omni_k8s_protect", "omni_direct"), ("omni_k8s_throughput", "omni_k8s_protect"),
                 ("omni_k8s_throughput", "omni_k8s_throughput_no_dynamics"), ("omni_k8s_throughput", "omni_k8s_throughput_no_gate")):
        if x in arms and y in arms:
            comps[f"{x}_vs_{y}"] = [paired(rows, y, x, m, rng) for m in HIGHER + LOWER]
    for abl in ("omni_direct_no_dynamics", "omni_direct_no_shield", "omni_pipeline"):
        if abl in arms and "omni_direct" in arms:
            comps[f"omni_direct_vs_{abl}"] = [paired(rows, abl, "omni_direct", m, rng) for m in HIGHER + LOWER]
    tails = {a: {"time_healthy_p05": float(np.percentile([r["time_healthy"] for r in rows if r["arm"] == a], 5)),
                 "recovery_minutes_p95": float(np.percentile([r["recovery_minutes"] for r in rows if r["arm"] == a], 95)),
                 "sla_violation_physical_p95": float(np.percentile([r["sla_violation_physical"] for r in rows if r["arm"] == a], 95)),
                 "energy_kwh_p95": float(np.percentile([r["energy_kwh"] for r in rows if r["arm"] == a], 95)),
                 "time_healthy_min": float(min(r["time_healthy"] for r in rows if r["arm"] == a)),
                 "recovered_fraction": float(np.mean([r["recovered"] for r in rows if r["arm"] == a]))} for a in arms}
    obs_identical = None
    k8s_obs_identical = None
    if "omni_k8s_observe" in arms and "k8s_ref_70" in arms:
        tk = {r["scenario_id"]: r["trace_hash"] for r in rows if r["arm"] == "k8s_ref_70"}
        to2 = {r["scenario_id"]: r["trace_hash"] for r in rows if r["arm"] == "omni_k8s_observe"}
        k8s_obs_identical = sum(tk[i] == to2[i] for i in tk)
    if "omni_observe" in arms:
        tn = {r["scenario_id"]: r["trace_hash"] for r in rows if r["arm"] == "native"}
        to = {r["scenario_id"]: r["trace_hash"] for r in rows if r["arm"] == "omni_observe"}
        obs_identical = sum(tn[i] == to[i] for i in tn)
    fam = {}
    for f in sorted({r["family"] for r in rows}):
        fam[f] = {a: {m: float(np.mean([r[m] for r in rows if r["arm"] == a and r["family"] == f]))
                      for m in ("time_healthy", "sla_violation_physical", "recovery_minutes", "contradictions", "energy_kwh")}
                  for a in ("native", "k8s_ref_70", "omni_k8s_protect", "omni_k8s_throughput") if a in arms}
    summary = {"scenarios": len(scns), "steps": cfg.steps, "seed_base": seed, "arms": arms,
               "allocation_law": asdict(law), "means": means, "paired": comps, "by_family": fam,
               "observe_mode_identical_to_native": obs_identical,
               "layered_observe_identical_to_kubernetes": k8s_obs_identical, "tails": tails}
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=500)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    s = run(a.scenarios, a.seed, Path(a.out), AllocationLaw())
    print(json.dumps({k: {m: round(v, 4) for m, v in s["means"][k].items()} for k in s["arms"]}, indent=1))
    print("observe identical to native:", s["observe_mode_identical_to_native"], "/", s["scenarios"])


if __name__ == "__main__":
    main()
