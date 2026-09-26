"""Build the Omni-Compass benchmark report (Markdown, then PDF via pilot/bench_pdf.py).

Three architectures, every gauge, every study in this repository:
  A  Kubernetes alone
  B  Kubernetes + Omni-Compass (Omni governs on top; Kubernetes' own controllers keep running)
  C  Omni-Compass direct (Omni is the single authority; the separate managers do not decide)

Inputs: results/heldout_seed_*/SUMMARY.json (pre-registered, 2 x 500 scenarios), a k8s_controlplane run (rows JSON),
results/fleet/planetlab or a planetlab SUMMARY.json, the live kind results (--live JSON), results/VERIFY_LOG.txt.

python tools/full_report.py --cp-rows ROWS.json --planetlab SUMMARY.json --live LIVE.json --out docs/BENCHMARK_REPORT.md
"""
from __future__ import annotations

import argparse, json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ["346410161", "360555127"]

HELD = [  # (label, key, higher_is_better, unit/format)
    ("ENERGY AND POWER", None, None, None),
    ("Energy per scenario (kWh)", "energy_kwh", False, "{:.1f}"),
    ("Peak power (kW)", "peak_power_kw", False, "{:.1f}"),
    ("Node-hours", "node_hours", False, "{:.1f}"),
    ("Idle node-hours (powered, doing nothing)", "idle_node_hours", False, "{:.2f}"),
    ("Share of time over the power limit", "violation_power", False, "{:.3f}"),
    ("Power-cap travel (how much the cap moved)", "power_cap_travel", False, "{:.3f}"),
    ("HEAT", None, None, None),
    ("Share of time over the heat limit", "violation_heat", False, "{:.3f}"),
    ("Thermal travel (how far temperature swung)", "thermal_travel", False, "{:.3f}"),
    ("SPEED AND BACKLOG", None, None, None),
    ("Mean queue (work waiting)", "mean_queue", False, "{:.0f}"),
    ("95th-percentile queue (worst moments)", "p95_queue", False, "{:.0f}"),
    ("Share of time over the backlog limit", "violation_backlog", False, "{:.3f}"),
    ("RELIABILITY AND RECOVERY", None, None, None),
    ("Availability", "availability", True, "{:.4f}"),
    ("Share of time healthy", "time_healthy", True, "{:.3f}"),
    ("Share of incidents recovered", "recovered", True, "{:.3f}"),
    ("Recovery time (minutes)", "recovery_minutes", False, "{:.1f}"),
    ("Physical SLA breaches (power, heat, backlog)", "sla_violation_physical", False, "{:.3f}"),
    ("All SLA breaches", "sla_violation_total", False, "{:.3f}"),
    ("WEAR AND TEAR", None, None, None),
    ("Machines started", "machines_started", False, "{:.1f}"),
    ("Machines stopped", "machines_stopped", False, "{:.1f}"),
    ("Node start/stop events", "node_start_stop", False, "{:.1f}"),
    ("Machine round trips (stopped then restarted)", "machine_round_trips", False, "{:.2f}"),
    ("Scale reversals (flip-flops)", "scale_reversals", False, "{:.2f}"),
    ("CONTROL QUALITY AND SAFETY", None, None, None),
    ("Contradictory commands between managers", "contradictions", False, "{:.2f}"),
    ("Safety-rule (invariant) violations", "invariant_violations", False, "{:.2f}"),
    ("Invariant violations excluding power", "invariant_violations_ex_power", False, "{:.2f}"),
    ("Security violations", "security_violations", False, "{:.3f}"),
    ("Pages to on-call", "pages", False, "{:.3f}"),
    ("Human interventions required", "human_interventions", False, "{:.3f}"),
]
A, B, C = "k8s_ref_70", "omni_k8s_throughput", "omni_direct"


def pct(a, b):
    if a == 0:
        return "0%" if b == 0 else "new"
    r = 100 * (b - a) / abs(a)
    return f"{r:+.2f}%" if abs(r) < 1 else f"{r:+.0f}%"


def verdict(entries, higher):
    """entries: paired dicts for each seed. Significant only if both seeds' CIs exclude zero in the same direction."""
    sig = []
    for e in entries:
        lo, hi = e["ci95"]
        if lo > 0:
            sig.append("up")
        elif hi < 0:
            sig.append("down")
        else:
            sig.append("ns")
    if all(s == sig[0] for s in sig) and sig[0] != "ns":
        good = (sig[0] == "up") == higher
        return "better" if good else "worse"
    return "not significant" if all(s == "ns" for s in sig) else "mixed"


def held_out():
    S = [json.load(open(ROOT / f"results/heldout_seed_{s}/SUMMARY.json")) for s in SEEDS]
    mean = lambda arm, k: float(np.mean([s["means"][arm][k] for s in S]))
    pair = lambda cand, k: [next(e for e in s["paired"][f"{cand}_vs_{A}"] if e["metric"] == k) for s in S]
    rows = ["| Gauge | A. Kubernetes alone | B. Kubernetes + Omni-Compass | C. Omni-Compass direct | B vs A | C vs A |",
            "|---|---:|---:|---:|---|---|"]
    tally = {"B": {"better": 0, "worse": 0, "same": 0}, "C": {"better": 0, "worse": 0, "same": 0}}
    for lab, k, hi, f in HELD:
        if k is None:
            rows.append(f"| **{lab}** | | | | | |"); continue
        a, b, c = mean(A, k), mean(B, k), mean(C, k)
        cells = []
        for tag, cand, v in (("B", B, b), ("C", C, c)):
            try:
                P = pair(cand, k)
                vd = verdict(P, hi)
                n_b = sum(e["better"] for e in P); n_w = sum(e["worse"] for e in P); n = sum(e["n"] for e in P)
                cells.append(f"{pct(a, v)} {vd} (better in {n_b}, worse in {n_w} of {n})")
                tally[tag]["better" if vd == "better" else "worse" if vd == "worse" else "same"] += 1
            except (StopIteration, KeyError):
                cells.append(pct(a, v))
        rows.append(f"| {lab} | {f.format(a)} | {f.format(b)} | {f.format(c)} | {cells[0]} | {cells[1]} |")
    obs = [(s["observe_mode_identical_to_native"], s["layered_observe_identical_to_kubernetes"]) for s in S]
    abl = {}
    for s in S:
        for x in ("omni_direct_vs_omni_direct_no_dynamics", "omni_direct_vs_omni_direct_no_shield"):
            for e in s["paired"].get(x, []):
                abl.setdefault((x, e["metric"]), []).append(e)
    native = {k: mean("native", k) for _, k, _, _ in HELD if k}
    return rows, tally, obs, abl, native, mean


def cp_study(rows_path):
    R = json.load(open(rows_path)); by = {}
    for r in R:
        by.setdefault(r["arm"], {})[r["scenario_id"]] = r
    ids = sorted(by["hpa70_ca"])
    G = [("Energy (kWh)", "energy_kwh", False), ("Peak power (kW)", "peak_power_kw", False),
         ("Time over power limit", "violation_power", False), ("Time over heat limit", "violation_heat", False),
         ("Time healthy", "time_healthy", True), ("Recovery time (min)", "recovery_minutes", False),
         ("Physical SLA breaches", "sla_physical", False), ("Mean queue", "mean_queue", False),
         ("Machines started", "machines_started", False), ("Machines stopped", "machines_stopped", False),
         ("Scale reversals", "scale_reversals", False), ("Invariant violations", "invariant_violations", False),
         ("Pages to on-call", "pages", False)]
    arms = [("A. Kubernetes alone (HPA + Cluster Autoscaler)", "hpa70_ca"),
            ("Reference: HPA + Karpenter-lite", "hpa70_karpenter"),
            ("B. Kubernetes + Omni-Compass (HPA target + CA gate)", "omni_target_gate_hpa70_ca"),
            ("C. Omni-Compass authority (HPA target, nodes, power cap)", "omni_throughput_full")]
    out = ["| Gauge | " + " | ".join(a for a, _ in arms) + " | C vs A (95% CI, wins of 24) |", "|---|" + "---:|" * len(arms) + "---|"]
    rng = np.random.default_rng(7)
    for lab, k, hi in G:
        vals = [np.mean([by[arm][i][k] for i in ids]) for _, arm in arms]
        a = np.array([by["hpa70_ca"][i][k] for i in ids]); c = np.array([by["omni_throughput_full"][i][k] for i in ids])
        d = c - a; bs = d[rng.integers(0, len(d), (4000, len(d)))].mean(1); lo, hi_ = np.percentile(bs, [2.5, 97.5])
        v = ("better" if (lo > 0) == hi else "worse") if (lo > 0 or hi_ < 0) else "not significant"
        wins = int(((c > a) if hi else (c < a)).sum())
        out.append(f"| {lab} | " + " | ".join(f"{x:.3f}" if abs(x) < 10 else f"{x:.1f}" for x in vals) +
                   f" | {pct(vals[0], vals[3])} {v} [{lo:+.3f}, {hi_:+.3f}], {wins} of 24 |")
    obs = sum(by["omni_observe_hpa70_ca"][i]["trace_hash"] == by["hpa70_ca"][i]["trace_hash"] for i in ids)
    return out, obs, len(ids)


def planetlab(path):
    d = json.load(open(path)); m = d["means"]
    arms = [("A. Kubernetes alone (HPA 0.7 + CA)", "k8s_hpa70_ca"), ("Reference: HPA 0.7 + Karpenter-lite", "k8s_hpa70_karpenter"),
            ("B. Kubernetes + Omni-Compass (HPA target)", "omni_target"), ("C. Omni-Compass node-pool authority (CA off)", "omni_fleet")]
    keys = [("Energy (kWh)", "energy_kwh"), ("Time healthy", "time_healthy"), ("Work completed", "work_completed"),
            ("Backlog violations", "violation_backlog"), ("Node reversals", "node_reversals"), ("Machines started", "machines_started")]
    out = ["| Gauge | " + " | ".join(a for a, _ in arms) + " |", "|---|" + "---:|" * len(arms)]
    for lab, k in keys:
        out.append(f"| {lab} | " + " | ".join(f"{m[a][k]:.4f}" if m[a][k] < 10 else f"{m[a][k]:.2f}" for _, a in arms) + " |")
    ver = ["| Comparison | Metric | Change | 95% CI | Verdict |", "|---|---|---:|---|---|"]
    for p in ("omni_target_vs_k8s_hpa70_ca", "omni_fleet_vs_k8s_hpa70_ca", "omni_fleet_vs_k8s_hpa70_karpenter"):
        for e in d["paired"][p]:
            ver.append(f"| {p.replace('_vs_', ' vs ')} | {e['metric']} | {e['delta']:+.4f} | [{e['ci95'][0]:+.4f}, {e['ci95'][1]:+.4f}] | {e['verdict']} |")
    return out, ver, d["observe_identical"], d["scenarios"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cp-rows", required=True); ap.add_argument("--planetlab", required=True)
    ap.add_argument("--live", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    live = json.load(open(a.live))
    hrows, tally, hobs, abl, native, hmean = held_out()
    crows, cobs, cn = cp_study(a.cp_rows)
    prows, pver, pobs, pn = planetlab(a.planetlab)
    verify = (ROOT / "results/VERIFY_LOG.txt").read_text().splitlines()
    n_pass = sum(1 for l in verify if l.startswith("PASS")); n_fail = sum(1 for l in verify if l.startswith("FAIL"))
    E = lambda arm: hmean(arm, "energy_kwh")
    L = []
    w = L.append
    w("# Omni-Compass: Kubernetes alone, Kubernetes + Omni-Compass, and Omni-Compass direct")
    w("")
    w("Benchmark report, 26 September 2026. Repository: Omni-Compass/The-Omni-Compass-Control-Core-Engine (private), branch "
      "claude/kubernetes-clusters-docker-stack-gp26ve. Every number below is produced by code in that repository and can be "
      "regenerated; section 18 gives the commands. Each result states whether it was **measured on a live Kubernetes control plane** "
      "or **computed in simulation**.")
    w("")
    w("## 1. Summary")
    w("")
    w("Omni-Compass is a single control engine that senses the whole compute stack and drives its actuators (its \"muscles\": "
      "replica counts, node pools, power caps and others) from one six-state dynamical model, with a safety shield before every "
      "action and a kill switch that hands control back. It was compared in three architectures:")
    w("")
    w("- **A. Kubernetes alone.** Kubernetes' own controllers decide: Horizontal Pod Autoscaler (HPA) for replicas, Cluster Autoscaler "
      "for nodes; other managers act on their own proposals.")
    w("- **B. Kubernetes + Omni-Compass.** Kubernetes' controllers keep running; Omni-Compass governs on top of them (sets the HPA "
      "target, gates and sizes the node pool, caps power) as the single authority over their settings.")
    w("- **C. Omni-Compass direct.** Omni-Compass is the only decision-maker and actuates the muscles directly; the separate managers "
      "no longer decide.")
    w("")
    w(f"**Main result (pre-registered, 1,000 held-out scenarios, simulation).** Against Kubernetes alone, B used "
      f"{pct(E(A), E(B))} energy and C {pct(E(A), E(C))}; time healthy rose from {hmean(A,'time_healthy'):.0%} to "
      f"{hmean(B,'time_healthy'):.0%} (B) and {hmean(C,'time_healthy'):.0%} (C); recovery time fell from "
      f"{hmean(A,'recovery_minutes'):.0f} to {hmean(B,'recovery_minutes'):.0f} and {hmean(C,'recovery_minutes'):.0f} minutes; "
      f"contradictory commands, pages and human interventions went to zero in both; safety-rule violations fell from "
      f"{hmean(A,'invariant_violations'):.1f} to {hmean(B,'invariant_violations'):.1f} (B) and {hmean(C,'invariant_violations'):.1f} (C). "
      f"Of {len([h for h in HELD if h[1]])} gauges, B is significantly better on {tally['B']['better']} and worse on {tally['B']['worse']}; "
      f"C is better on {tally['C']['better']} and worse on {tally['C']['worse']}.")
    w("")
    lv = live["side_by_side"]
    w(f"**Live Kubernetes result (measured).** Two identical Kubernetes clusters (1 control plane + 6 workers) ran the same load at the "
      f"same time, one without Omni-Compass and one with it. With Omni-Compass: worker nodes in service {lv['nodes_native']:.1f} to "
      f"{lv['nodes_omni']:.1f}; utilisation of the workers in service {lv['util_native']:.3f} to {lv['util_omni']:.3f}. **Energy:** with the "
      f"parked workers kept on standby, powered and ready ({lv['standby_note']}), energy was {lv['energy_native_wh']:.0f} vs "
      f"{lv['energy_omni_wh']:.0f} Wh ({pct(lv['energy_native_wh'], lv['energy_omni_wh'])}): parking alone saves essentially nothing; "
      f"energy per unit of work {lv['epc_change']}. The -43% first reported for this run holds only if parked workers are powered "
      f"off. Waiting pods and HPA shortfall were not significantly different. The kill switch restored the original HPA target (50) and all 6 workers.")
    w("")
    w("**Where Omni-Compass costs something.** In the pre-registered study both B and C keep more node-hours powered than "
      "Kubernetes alone and start and stop machines more often (more wear), and move the power cap more; C also lets more work wait "
      "in the queue and flips scale direction more often. In that study the energy saving comes from power capping and load "
      "shaping, not from switching machines off. On the live cluster the saving came from switching machines off. Other limits: "
      "the small-cluster release band (section 11); power and heat on the live cluster are modelled, not metered.")
    w("")
    w("**Trade-off in one line:** B is the strongest all-round result in simulation (energy, health, recovery, queue, coordination and safety "
      "all better; wear and node-hours worse); C is the strongest on peak power, heat and safety (zero invariant violations) at the "
      "cost of queue length, wear and flip-flops. These are the gauges to tune next.")
    w("")
    w("## 2. What Omni-Compass is")
    w("")
    w("### 2.1 The engine")
    w("The engine is a six-state ordinary differential equation system, state x = (E, U, I_U, S, B, B_dot): error E, coherence U, "
      "pressure I_U, stress S and a damped bath B. The shipped core (`omnicompass/core.py`) integrates it with fourth-order "
      "Runge-Kutta and holds the control input constant across the four stages:")
    w("")
    w("```")
    for ln in ["(1) dE/dt   = -alpha_E E + beta_int + beta_ext + v_eff",
               "(2) dU/dt   = mu U (1 - U^2) - (dE/dt)/E_max - lambda_U U + u,   |u| <= 25",
               "(3) dI_U/dt = (1 - U) - sigma_1 E - delta S - lambda_I I_U",
               "(4) v_eff   = cos(omega_B t / 2) c tanh(lambda_0 + lambda_1 (U - 0.5) + lambda_2 S)",
               "(5) Phi(S)  = alpha_s S^2/2 + beta_s S^3/4 - delta S",
               "(6) dS/dt   = -dPhi/dS",
               "(7) dB/dt = B_dot;  dB_dot/dt = gamma_c delta S - (omega_B/Q_B) B_dot - omega_B^2 B",
               "(8) R_B[n]  = finite-difference audit of (7), never fed back",
               "Controller: u = clip(-f_U(x,t) + 12 (sigma - U), -25, +25)"]:
        w(ln)
    w("```")
    w("Telemetry (load, queue, power, heat, network, drift, staleness, security) is assimilated into the state each decision; an "
      "allocation law turns the state into a demand target rho* (the HPA target), a node change, and a power cap. Release of capacity "
      "is gated by equation (2): capacity is only released once the control push has converged.")
    w("")
    w("### 2.2 The nervous system (muscles)")
    w("Each muscle has five parts: afferent (pull: sense), the shared engine, efferent (push: act), reflex (the shield checks every push) "
      "and kill (hand the muscle back to its own controller). Status in this repository: **wired live on Kubernetes** (sense and "
      "push executed through kubectl, each with shield and kill): nodes, HPA target, power cap (in-place CPU limits, enforced by "
      "the kernel), security hold, deployment rollouts (pause, resume, undo), batch queue (admit held Jobs); **sensed**: heat "
      "(harness heat law on live power, or GPU temperature), network; **hardware connectors** (built and tested with fake "
      "hardware, off on CI machines): CPU power states (RAPL read, cpufreq ceiling) and GPU (nvidia-smi power and temperature "
      "read, power limit); **open** (registered, no plant yet): memory, storage, cooling, grid, training, inference, agent "
      "containment and the rest of the 52-muscle domain map (`docs/DOMAIN_MAP.md`). AI value alignment is explicitly not an "
      "Omni-Compass muscle. Code: `omni_controller/controller.py`, `omni_controller/muscles.py`, `omnicompass/nervous.py`.")
    w("")
    w("### 2.3 The shield and the kill switch")
    w("Before any action the shield (`omnicompass/shield.py`) enforces invariants I1 to I5: no expansion during a security block, node "
      "count within bounds, step limits, never below the capacity running and pending work needs, and the site power limit. The kill "
      "switch (a file or `OMNI_KILL=1`) restores every HPA target Omni-Compass changed from the recorded original, returns the node pool "
      "to its native size and drops to observe mode. Every decision and action is written to an append-only audit log.")
    w("")
    w("### 2.4 Operating modes")
    w("Observe (compute and log, write nothing), target (write HPA targets), nodepool (also size a node pool). Laws: power_protect "
      "(enforce the site power envelope), throughput (power envelope not enforced; capacity sized at full power) and fleet variants "
      "tuned on the 15-second fleet harness.")
    w("")
    w("## 3. The three architectures, and how each study realises them")
    w("")
    w("| Study | A. Kubernetes alone | B. Kubernetes + Omni-Compass | C. Omni-Compass direct | Live or simulated |")
    w("|---|---|---|---|---|")
    w("| Pre-registered held-out stack benchmark (2 x 500 scenarios) | `k8s_ref_70`: documented HPA law (target 0.7, 10% tolerance, 300 s "
      "stabilisation) and Cluster Autoscaler (scale-up on backlog, remove after 10 min under 50%), other managers act on their own "
      "proposals | `omni_k8s_throughput`: the same Kubernetes loops, Omni governs on top | `omni_direct`: Omni senses and actuates "
      "the stack directly | simulation |")
    w(f"| Control-plane replica (24 scenarios) | `hpa70_ca`: metrics-server, HPA and Cluster Autoscaler replicas at 15 s | "
      "`omni_target_gate_hpa70_ca`: Omni writes the HPA target and gates Cluster Autoscaler scale-down | `omni_throughput_full`: Omni "
      "writes the HPA target, owns node scale-down and power cap; the Cluster Autoscaler may only add nodes | simulation |")
    w(f"| PlanetLab-shaped demand, fleet plant ({pn} scenarios) | `k8s_hpa70_ca` | `omni_target`: Omni writes the HPA target | "
      "`omni_fleet`: Omni is the node-pool authority, Cluster Autoscaler off | simulation on recorded traces |")
    w("| Live kind cluster, side by side | native: HPA only, 6 workers always on, Omni not running | Omni on top: sets the HPA target "
      "and is the sole node-pool authority (cordon, drain, uncordon); Kubernetes' scheduler, kubelet and HPA still execute | "
      "not yet built live (section 16) | **live** |")
    w("")
    w("## 4. Method and why the comparison is fair")
    w("")
    w("- **Frozen before testing.** The allocation law, engine parameters, shield limits, modes, baselines and benchmark code were "
      "selected on development seeds (1000, 2000) and frozen, with SHA-256 hashes and program fingerprints in "
      "`results/PREREGISTRATION.json`, before any run on the held-out seeds 346410161 and 360555127. `verify.py` re-checks every hash.")
    w("- **Same scenarios for every arm.** Each scenario is run under every architecture; comparisons are paired scenario by scenario.")
    w(f"- **Observe-identity check.** Omni-Compass in observe mode must produce a trajectory bit-identical to the arm it observes, "
      f"or the run is invalid. Held-out: {hobs[0][0]} and {hobs[1][0]} of 500 identical to the native stack, {hobs[0][1]} and "
      f"{hobs[1][1]} of 500 identical to Kubernetes; control-plane replica: {cobs} of {cn}; PlanetLab: {pobs} of {pn}; live: 0 writes "
      "while observing.")
    w("- **Statistics.** Differences are paired (Omni minus Kubernetes on the same scenario) with 95% bootstrap confidence intervals. "
      "In the held-out study a difference is called better or worse only if the interval excludes zero in the same direction on both "
      "independent seeds; 'better in N' counts scenarios. Live results use 2-minute blocks and a bootstrap over blocks.")
    w("- **Ablations** show the engine, not an accident of tuning, produces the result (section 5.3).")
    w("- **Independent implementations.** A C++ engine, governor, shield and HPA law are checked against the Python ones (section 8).")
    w("")
    w("## 5. Results: pre-registered held-out benchmark (1,000 scenarios, simulation)")
    w("")
    w("Mean over two held-out seeds x 500 scenarios; verdicts require both seeds to agree.")
    w("")
    L.extend(hrows)
    w("")
    w("### 5.1 What the numbers say")
    w(f"- **Energy:** B {pct(E(A), E(B))}, C {pct(E(A), E(C))} versus Kubernetes alone, although both keep slightly more "
      "node-hours powered. The saving comes from power capping and load shaping: time over the power limit halves (B) or nearly "
      "vanishes (C), and C cuts peak power by a quarter. Releasing idle machines, which the live cluster showed, is not what drives "
      "this study; idle node-hours are a gauge to tune.")
    w("- **Reliability:** time healthy and recovery improve sharply in both B and C; the share of incidents recovered rises.")
    w("- **Coordination:** separate managers issue contradictory commands (A); a single authority issues none (B, C). Pages and human "
      "interventions go to zero because Omni-Compass acts on the conditions that would have paged someone.")
    w("- **Heat:** C cuts time over the heat limit the most, because it governs power caps and load together.")
    w("- **Costs:** node start/stop events rise (B +66%, C +102%), machine round trips rise, the power cap moves more, and C's "
      "queue and scale reversals are higher than Kubernetes alone. The 24-scenario control-plane study (section 6) shows the "
      "opposite for wear (fewer machine stops), so wear depends on the plant and law and is a primary tuning target. These are "
      "reported, not tuned away.")
    w("")
    w("### 5.2 Architecture A has a hidden cost: the fragmented stack without Kubernetes")
    w(f"For reference, the stack with each manager acting alone and no Kubernetes loops (`native`) used {native['energy_kwh']:.1f} kWh, "
      f"was healthy {native['time_healthy']:.0%} of the time, took {native['recovery_minutes']:.0f} minutes to recover and produced "
      f"{native['contradictions']:.1f} contradictory commands and {native['invariant_violations']:.1f} invariant violations per "
      "scenario. Kubernetes already improves on that; Omni-Compass improves on Kubernetes.")
    w("")
    w("### 5.3 Ablations: is it the engine?")
    w("| Comparison | Metric | Mean difference | 95% CI (seed 1) | 95% CI (seed 2) |")
    w("|---|---|---:|---|---|")
    for (x, k), es in sorted(abl.items()):
        if k in ("energy_kwh", "time_healthy", "recovery_minutes", "invariant_violations", "mean_queue", "violation_heat"):
            w(f"| {x.replace('omni_direct_vs_', 'Omni direct vs ')} | {k} | {np.mean([e['mean_delta'] for e in es]):+.3f} | "
              f"[{es[0]['ci95'][0]:+.3f}, {es[0]['ci95'][1]:+.3f}] | "
              f"[{es[-1]['ci95'][0]:+.3f}, {es[-1]['ci95'][1]:+.3f}] |")
    w("")
    w("'no_dynamics' runs the same allocation law with equations (1) to (7) frozen; 'no_shield' removes the shield. The difference "
      "is full engine minus ablation: negative energy means the evolving dynamics save energy the frozen engine does not; the "
      "shield ablation shows what the shield prevents.")
    w("")
    w("## 6. Results: Kubernetes control-plane replica (24 scenarios, simulation)")
    w("")
    w("Replicas of the documented metrics-server, HPA (15 s) and Cluster Autoscaler (10 s) loops, with Karpenter-lite as a second "
      "Kubernetes reference; Omni-Compass decides every 300 s.")
    w("")
    L.extend(crows)
    w("")
    w("## 7. Results: live Kubernetes (measured)")
    w("")
    w("### 7.1 Side by side, two identical clusters at the same time")
    w("kind clusters (real Kubernetes API server, scheduler, kubelet, HPA and metrics-server), 1 control plane + 6 workers each; the "
      "official php-apache HPA workload (target 50); the same stepped load (1, 2, 3, 1, 2, 1 load generators over 20 minutes after a "
      "2-minute warm-up); capture every 15 s. Native: Omni-Compass not started. Omni: nodepool mode, HPA target, node pool, power "
      "sensing. Run 36209933218, 2026-09-26.")
    w("")
    w("| Gauge | Kubernetes alone | Kubernetes + Omni-Compass | Change |")
    w("|---|---:|---:|---:|")
    for lab, n, o, ch in live["gauges"]:
        w(f"| {lab} | {n} | {o} | {ch} |")
    w("")
    w("| Metric (per unit of work, 2-minute blocks) | Kubernetes alone | Kubernetes + Omni-Compass | Change | 95% CI | Verdict |")
    w("|---|---:|---:|---:|---|---|")
    for r in live["significance"]:
        w("| " + " | ".join(r) + " |")
    w("")
    w(f"Omni-Compass decisions: nodes per minute {live['nodes_decided']}; HPA target {live['hpa_target']}. Node-pool resizes: 3 "
      "(three workers cordoned and drained, their pods rescheduled by Kubernetes). Kill switch: HPA target restored to 50, 6 of 6 "
      "workers back in service.")
    w("")
    w("### 7.2 Other live runs")
    w("| Run | Setup | Result |")
    w("|---|---|---|")
    for r in live["other_runs"]:
        w("| " + " | ".join(r) + " |")
    w("")
    w("## 8. Engineering verification")
    w("")
    w(f"`python verify.py` runs {n_pass} checks ({n_fail} failures in the recorded log `results/VERIFY_LOG.txt`), including:")
    w("")
    for key in ("SHA-256", "core parity", "C++ core vs 500 fixtures", "C++ governor vs Python governor (throughput)",
                "C++ shield vs Python shield", "negative control", "independent C++ HPA", "soak test (throughput), 100,000,000",
                "observe", "kill"):
        for l in verify:
            if l.startswith("PASS") and key in l:
                w(f"- {l[4:].strip()}"); break
    w("")
    w("Also tested: the live controller against a fake cluster (observe writes nothing; targets bounded; kill restores from the "
      "HPA annotation after a restart; node pool bounded and dry-run safe), the full-engine options (parked and control-plane nodes "
      "excluded; the kill switch restores the node pool exactly once) and pilot scoring (detects a real gain, reports no gain on "
      "identical clusters, detects a service regression).")
    w("")
    w("## 9. Physics and models")
    w("")
    w("- **Stack plant power:** each node draws idle 0.38 kW plus 1.12 kW x utilisation; a power cap throttles delivered capacity.")
    w("- **Heat:** thermal state follows a first-order lag toward 0.34 + 0.62 x power stress (time constant about 7 steps); heat above "
      "0.82 throttles capacity; 'over the heat limit' means thermal above 1.03.")
    w("- **Live kind cluster:** kind nodes have no power meter, so power is a declared model: 100 W idle + 150 W x CPU utilisation per "
      "worker in service, plus a standby power for each parked (cordoned and drained) worker. Standby defaults to the idle power "
      "(the worker stays powered and ready); lower values apply only to a declared sleep state, zero only to machines really powered "
      "off. The first live reports counted parked workers as zero; section 7.1 gives both. The same constants drive the governor's "
      "power sense and the energy score, so they cannot disagree. On real hardware this is replaced by metered power (RAPL, PDU or BMC).")
    w("- **Savings model** (`results/SAVINGS.csv`): a 1,000-node web cluster at 0.4 kW per node, PUE 1.4, $0.12/kWh and 0.4 kg CO2/kWh; "
      "reduction versus HPA 0.7 + Karpenter-lite of 14% to 20% (fleet plant) gives roughly 710 to 960 MWh, $85,000 to $115,000 and "
      "280 to 380 t CO2 per year.")
    w("- **Engine overhead:** about 2.9 microseconds per decision in C++, memory flat over 100 million decisions.")
    w("")
    w("## 10. What is proven, what is simulated, what is not claimed")
    w("")
    w("| Claim | Status | Evidence |")
    w("|---|---|---|")
    for r in [("Engine equations are finite and deterministic; C++ equals Python", "Proven", "verify.py, 500 fixtures, max error 3.6e-15"),
              ("Observe mode changes nothing", "Proven (simulation and live)", "bit-identical trajectories; 0 writes live"),
              ("Kill switch restores native control", "Proven (simulation and live)", "HPA target 50 and all workers restored live"),
              ("Omni-Compass acts on a real Kubernetes control plane (HPA target, node pool)", "Proven live", "section 7"),
              ("Fewer nodes in service than Kubernetes with a fixed node pool, same load served", "Measured live", "section 7.1"),
              ("Lower energy on the live cluster", "Not shown while parked nodes stay on standby; -22% to -43% only if parked nodes sleep or power off", "section 7.1"),
              ("Better energy, health, recovery, coordination than Kubernetes (HPA + CA)", "Pre-registered simulation", "section 5"),
              ("Better than Karpenter-lite on energy", "Simulation", "sections 6, and PlanetLab fleet plant"),
              ("Better than upstream Karpenter or Cluster Autoscaler binaries, live", "Not yet tested", "section 12"),
              ("Metered energy savings on physical servers", "Not yet tested", "power is modelled"),
              ("GPU power-limit muscle saves 15-19% energy with <1% slower responses", "Simulation calibrated to metered H100 data (MLPerf)", "section 12"),
              ("CPU frequency muscle", "Simulation (uncalibrated): about -3.5% energy, -67% heat", "section 12"),
              ("Tuned laws remove wear and node-hour negatives (C-throughput)", "Pre-registered amendment, new held-out data", "section 13"),
              ("Cooling, grid, memory, storage and the other open muscles", "Not claimed", "no plant or connector yet"),
              ("Makes AI models aligned or trustworthy", "Not claimed", "value alignment is outside Omni-Compass")]:
        w("| " + " | ".join(r) + " |")
    w("")
    w("## 11. Limits and threats to validity")
    w("")
    for s in ["Simulated studies use documented-behaviour replicas of Kubernetes controllers, not the upstream binaries; the "
              "Kubernetes reference omits Karpenter consolidation, VPA, scheduling constraints and disruption budgets.",
              "The live cluster is kind: nodes are containers on one CI machine; the two live arms ran on two machines at the same "
              "time, so machine-to-machine variation is part of the noise; each live arm is 20 minutes, one repetition.",
              "Live power and heat are modelled; parked kind workers are drained containers. If parked machines must stay on "
              "standby, parking reduces nodes in service but not energy; live energy savings then have to come from power caps, CPU "
              "power states and heat control, which are not yet wired live.",
              "The live native arm had no node autoscaler, so its node pool was always full; the fair live opponent is Karpenter or "
              "Cluster Autoscaler (section 16).",
              "The live significance for energy per core-hour with standby power is computed from minute averages (10 two-minute "
              "blocks), not from the 15-second capture.",
              "The fleet law releases a node only when the pool has more than three nodes of slack; a three-worker pool cannot scale "
              "down (observed live, reproduced offline). Small clusters need a pool-size-aware release band.",
              "Architecture C was measured in simulation only; the live C (Kubernetes' controllers parked, Omni-Compass as the only "
              "brain) is not built yet.",
              "Service quality differences in the live runs (pending pods, HPA shortfall) are not statistically significant at "
              "this run length."]:
        w(f"- {s}")
    w("")
    # ---------------- device plant (GPU power limit, CPU frequency) ----------------
    hw = json.loads((ROOT / "results/hardware/SUMMARY.json").read_text()); cal = json.loads((ROOT / "results/hardware/CALIBRATION_MLPERF.json").read_text())
    w("## 12. GPU and CPU muscles: device plant calibrated to metered hardware (simulation)")
    w("")
    w("The GPU power-limit and CPU frequency muscles cannot be actuated on CI machines (no GPU; the hypervisor hides RAPL and "
      "cpufreq). Their connectors are built (section 2.2) and this plant shows what they do. **GPU calibration:** the "
      "performance-versus-power-limit exponent is fitted to MLPerf Inference v4.0 results for an NVIDIA DGX-H100 (8 x H100-SXM, "
      "700 W TDP), MaxQ (power-limited with `nvidia-smi -pl`, the same command the Omni-Compass GPU connector sends) versus "
      "MaxP, system power metered by a Yokogawa WT333E; Apache 2.0. Fitted exponent " + f"{cal['gamma_min']:.3f} to {cal['gamma_max']:.3f} (median {cal['gamma_median']:.3f}); "
      "all three are run. **CPU:** a standard first-order model (dynamic power ~ frequency cubed) against a schedutil-style "
      "governor; not calibrated to metered data yet. **S** is a fixed manual 70% cap, what an operator could do by hand. "
      "24 scenarios, 8 load families; * = paired 95% interval excludes zero.")
    w("")
    w("| Vessel | Gauge | A. Native | S. Fixed 70% cap | B. + Omni-Compass | C. Omni-Compass direct |")
    w("|---|---|---:|---:|---:|---:|")
    labels = [("energy_kwh", "Energy (kWh)"), ("kwh_per_work", "Energy per unit of work"), ("p95_latency_x", "95th-pct response time (x baseline)"),
              ("slo_breach_min", "Minutes over service target"), ("heat_over_min", "Minutes over heat limit"), ("peak_kw", "Peak power (kW)"),
              ("power_over_min", "Minutes near full power")]
    for vn, v in hw["vessels"].items():
        m = v["means"]
        for k, lab in labels:
            a = m["A"][k]
            cell = lambda arm: f"{m[arm][k]:.3f} ({pct(a, m[arm][k])}{'*' if v['paired_vs_A'][arm][k]['significant'] else ''})"
            w(f"| {vn} | {lab} | {a:.3f} | {cell('S')} | {cell('B')} | {cell('C')} |")
    w("")
    w("**Reading:** on GPUs Omni-Compass saves 15-19% energy across the measured range with response time 0.6-0.8% slower; a "
      "fixed cap saves about the same energy but slows responses 30-63% and misses the service target. On CPUs the native "
      "governor already tracks demand, so frequency control alone saves about 3.5%; its main effect is heat (-67%). CPU "
      "frequency control is below the 10% bar and is a physical ceiling of that muscle, not a tuning gap.")
    w("")
    # ---------------- amendment ----------------
    am = json.loads((ROOT / "tuning/HELDOUT_AMENDMENT.json").read_text())
    w("## 13. Amendment: tuned laws, frozen, then tested on new held-out data (simulation)")
    w("")
    w("Two law variants were tuned on the development seeds only (1000, 2000; `tuning/SEARCH*.json`), frozen with SHA-256 hashes "
      "in `tuning/PREREGISTRATION_AMENDMENT_2026-09-26.json` and pushed (commit b79d1dd, 03:17 UTC) before a single run on new "
      "held-out seeds 731001 and 731002 (2 x 500 scenarios). The frozen engine files are unchanged; the original pre-registered "
      "result (section 5) stays the primary result. B-wear: node release held longer. C-throughput: Omni-Compass direct under "
      "the throughput law with a wider release band and engine-gated cap. + better, ! worse (both seeds agree), blank not significant.")
    w("")
    names = ["B_frozen", "B_wear", "C_frozen", "C_throughput"]
    w("| Gauge | A. Kubernetes alone | " + " | ".join(names) + " |")
    w("|---|---:|" + "---:|" * len(names))
    A0 = am["means"]["A_k8s"]
    for k in A0:
        cells = []
        for n in names:
            vv = am["means"][n][k]; vd = am["paired"][n][k]["verdict"]
            cells.append(f"{vv:.3f} ({pct(A0[k], vv)}){' +' if vd == 'better' else ' !' if vd == 'worse' else ''}")
        w(f"| {k} | {A0[k]:.3f} | " + " | ".join(cells) + " |")
    w("")
    w("Worse gauges: " + ", ".join(f"{n} {sum(v['verdict'] == 'worse' for v in am['paired'][n].values())}" for n in names) + ".")
    w("")
    # ---------------- every negative ----------------
    w("## 14. Every negative, its cause and its status")
    w("")
    w("| Negative | Where | Status | Cause | What would fix it |")
    w("|---|---|---|---|---|")
    for r in [
        ("Node start/stop cycles (wear)", "B, pre-registered", "reduced (+65% to +34%), not removed", "node release thresholds are fixed numbers", "hybrid: Kubernetes serves the queue, Omni releases nodes with the C-throughput law (removed wear there: -50%)"),
        ("Node start/stop, round trips, reversals", "C, pre-registered", "fixed in C-throughput (new held-out)", "power-protect law released nodes too eagerly", "adopted in C-throughput"),
        ("Node-hours and idle node-hours", "B and C, pre-registered", "fixed in C-throughput (-10%, -23%); not in B", "power capping trades lower watts for more servers on", "hybrid as above; node-aware cap"),
        ("Queue / backlog / availability -0.3%", "C (both variants)", "UNRESOLVED", "not the replica law and not the sizing constants (both tested); likely the delayed observation or direct-mode proposals", "trace one scenario step by step; candidate: feed the queue into the engine without the extra delay"),
        ("Power-cap movement", "B and C", "inherent", "moving the cap is how capping saves energy; freezing it removed most of the saving (tested: -28% to -2%/-7%)", "none needed: electronic setting, no physical wear; reported"),
        ("CPU frequency saving 3.5%", "device plant", "physical ceiling", "the native Linux governor already follows demand", "value is in heat (-67%) and in combining with power caps"),
        ("GPU node on/off saving 3%", "fleet plant", "superseded", "training nodes cannot be switched off", "the GPU power-limit muscle (15-19%)"),
        ("Live energy with parked servers on standby ~0%", "live kind", "open", "parked servers still draw standby power", "live power cap and CPU/GPU muscles; sleep states where hardware allows"),
        ("Small clusters (<= 3 workers) never release", "live kind", "open", "fleet law release band of 3 nodes", "pool-size-aware release band (law change)"),
        ("Pages in the 24-scenario replica", "control-plane replica", "open", "longer queue triggers the page rule", "same as queue"),
    ]:
        w("| " + " | ".join(r) + " |")
    w("")
    w("## 15. The industry problem map: what Omni-Compass is aimed at")
    w("")
    w("One engine; the vessel (the plant it sits on) is the only thing that changes. Industry figures are approximate, from the "
      "public sources named, and are context, not results of this report. Status: **live** = measured on a real Kubernetes control "
      "plane; **sim** = demonstrated in this repository's simulations; **open** = mapped, connector not built.")
    w("")
    w("| Problem | Scale in the industry (approximate, source) | Best software today | Omni-Compass vessel and muscles | Gauge that shows it | Status |")
    w("|---|---|---|---|---|---|")
    for r in [
        ("Data-centre electricity growth", "about 415 TWh in 2024, about 1.5% of world electricity, projected near 945 TWh by 2030 (IEA, Energy and AI, 2025)",
         "Karpenter, Cluster Autoscaler, CAST AI, Spot Ocean; Kepler for metering", "compute vessel: nodes, HPA, power cap", "energy, node-hours, idle node-hours",
         "sim; live only where parked nodes can sleep or power off"),
        ("Idle and over-provisioned capacity", "Kubernetes clusters commonly run near 10-15% average CPU utilisation (CAST AI and Datadog industry reports); roughly a quarter to a third of cloud spend reported as waste (Flexera State of the Cloud)",
         "VPA, Goldilocks, StormForge, Kubecost/OpenCost", "compute vessel: nodes, HPA; memory (open)", "utilisation, node-hours per core-hour", "live + sim"),
        ("Controllers fighting each other", "documented conflicts, e.g. HPA and VPA on the same CPU metric (Kubernetes documentation advises against it)",
         "none: each tool decides alone", "single authority over all muscles", "contradictory commands, scale reversals", "sim"),
        ("Outages and slow recovery", "most significant outages cost over $100,000 (Uptime Institute annual outage analysis)",
         "Argo Rollouts, Flagger, SRE runbooks, AIOps (Dynatrace, Datadog)", "compute vessel + deployments (partial)", "time healthy, recovery time, SLA breaches", "sim"),
        ("On-call load and alert fatigue", "widely reported burnout in SRE surveys", "PagerDuty, alert tuning", "all muscles: act before the page", "pages, human interventions", "sim"),
        ("Heat and cooling limits", "cooling is a large share of facility energy; average PUE about 1.5 (Uptime Institute survey)",
         "DCIM (Schneider EcoStruxure), DeepMind cooling AI (reported about 40% less cooling energy)", "heat (sensed), cooling plant (open)", "time over heat limit, thermal travel", "sim"),
        ("Site power and grid-connection limits", "multi-year waits for new grid connections are widely reported", "Meta Dynamo power capping, Intel RAPL",
         "power cap (wired), batteries and demand response (open)", "peak power, time over power limit", "sim"),
        ("GPU energy and power limits", "GPU fleets widely reported well below full utilisation; H100 TDP 700 W", "NVIDIA DCGM and MIG, Run:ai, Kueue; manual MaxQ power limits",
         "GPU power-limit muscle (hardware connector)", "energy per unit of work, response time, heat", "sim, calibrated to MLPerf metered H100 data: -15% to -19% energy, +0.6-0.8% response time"),
        ("Batch deadlines and fair sharing", "", "Kueue, Volcano, Slurm", "batch queue muscle (open)", "missed deadlines, queue wait", "open"),
        ("Hardware wear", "power cycling and churn shorten component life", "none as a governed objective", "nodes: start/stop cycles and reversals",
         "machines started and stopped, round trips", "mixed: better in the 24-scenario study, worse in the held-out study; tuning target"),
        ("Carbon reporting and reduction", "regulatory disclosure is expanding", "Google carbon-aware computing, Kepler", "carbon-aware placement (open)", "kWh and CO2 per unit of work", "sim (modelled)"),
        ("Runaway AI agents and spend", "", "per-tool quotas and permissions", "agent containment vessel (open)", "caps hit, kills, spend", "open"),
    ]:
        w("| " + " | ".join(r) + " |")
    w("")
    w("## 16. What comes next")
    w("")
    for s in ["Live architecture C: park HPA, VPA, Cluster Autoscaler and Karpenter; Omni-Compass sets replicas, resources, "
              "placement, priorities and quotas directly; Kubernetes keeps execution and reflexes (restarts, rescheduling); the kill "
              "switch wakes the parked controllers.",
              "Live opponent at full strength: Karpenter (kwok provider) and Cluster Autoscaler in architecture A.",
              "24 live scenarios (traffic, failures, power and heat limits, batch and AI, growth, mixed) with repetitions.",
              "More muscles two-way: CPU power states, memory, batch queues, network, security, then GPU and cooling on hardware.",
              "Metered power on physical machines."]:
        w(f"- {s}")
    w("")
    w("## 17. Questions and answers")
    w("")
    qa = [
        ("Does Omni-Compass replace Kubernetes?", "No. Kubernetes keeps running containers, placing pods, restarting failures and "
         "networking. Omni-Compass replaces the separate decision loops (how many replicas, how many nodes, what power) with one "
         "authority. In architecture C Kubernetes becomes one muscle."),
        ("What happens if Omni-Compass crashes or is switched off?", "The kill switch restores every setting it changed and returns "
         "control to Kubernetes' own controllers; this was exercised live and in simulation. A crashed controller writes nothing further."),
        ("Can it make things worse?", "Every action passes the shield first; it never goes below the capacity running and pending work "
         "needs, and never changes more than the step limit. In the held-out benchmark it had fewer safety violations than Kubernetes. "
         "Its real costs are listed in sections 1 and 5.1."),
        ("How fast does it decide, and what does it cost to run?", "One decision per 60 s on live Kubernetes (300 s in the replica), "
         "with a 15 s fast path that adds nodes for pending pods. The engine takes about 2.9 microseconds per decision."),
        ("Why does it save energy?", "In the pre-registered stack study mainly by power capping and load shaping (fewer minutes over "
         "the power limit, lower peak), while keeping slightly more machines on. On the live cluster it took machines out of service "
         "(6 to 3 workers) and packed replicas more densely; that saves energy only if the parked machines sleep or power off. With "
         "parked machines on standby the live saving was about zero, so live savings must come from power caps and CPU power states."),
        ("Does it slow applications down?", "In architecture B the queue is shorter than Kubernetes alone; in C it is longer. Live, "
         "response-time measurement is not yet in the capture; pending pods and HPA shortfall were not significantly different."),
        ("Is this tuned to the test?", "Parameters were selected on development seeds and frozen with hashes before the held-out seeds "
         "were run; verify.py fails if any frozen file changes."),
        ("How many scenarios and how certain?", "1,000 pre-registered held-out scenarios, 24 control-plane scenarios, PlanetLab traces "
         "and live runs; 95% bootstrap intervals, two independent seeds must agree."),
        ("What is measured versus modelled?", "Live: node counts, replicas, pods, CPU, the controller's actions and the kill switch. "
         "Modelled: power and heat everywhere, and everything in the simulated studies."),
        ("Is the mathematics sound?", "The core is a closed six-state system integrated with RK4; the C++ and Python implementations "
         "agree to 3.6e-15 on 500 reference trajectories; 100 million decisions ran without a non-finite value."),
        ("Who owns it and how can it be used?", "The Omni-Compass LLC. Free for evaluation, research and non-commercial use; commercial "
         "use requires a paid licence; protected by copyright and by patents and patent applications (see LICENSE and NOTICE)."),
        ("What is not claimed?", "Superiority over upstream Karpenter or Cluster Autoscaler live, metered savings on physical hardware, "
         "GPU or facility control, and anything about AI value alignment."),
        ("How do I check it myself?", "Run the commands in section 18; the live runs are GitHub Actions workflows in the repository."),
    ]
    for q, ans in qa:
        w(f"**{q}** {ans}")
        w("")
    w("## 18. Reproduce")
    w("")
    w("```")
    for c in ["pip install -r requirements.txt",
              "python verify.py                                        # all checks, hashes, parity, soak",
              "python benchmarks/stack_benchmark.py ...                # held-out stack benchmark (see HARNESS.md)",
              "python -m k8s_controlplane.benchmark --scenarios 24 --seed 424242",
              "python -m fleet.planetlab --dir fleet/traces/planetlab --scenarios 8 --out /tmp/pl",
              "GitHub Actions: benchmark (live side by side), live-kind-full, live-kind",
              "python tools/full_report.py ... && python pilot/bench_pdf.py docs/BENCHMARK_REPORT.md docs/BENCHMARK_REPORT.pdf"]:
        w(c)
    w("```")
    w("")
    w("## 19. Glossary")
    w("")
    for t, d in [("HPA", "Horizontal Pod Autoscaler: Kubernetes controller that sets replica counts from CPU utilisation versus a target."),
                 ("Cluster Autoscaler, Karpenter", "Kubernetes add-ons that add and remove nodes."),
                 ("Node, worker", "a machine (here a container in kind) that runs pods."),
                 ("Cordon, drain", "mark a node unschedulable, then move its pods elsewhere."),
                 ("kind", "Kubernetes in Docker: a real Kubernetes control plane whose nodes are containers."),
                 ("Observe mode", "Omni-Compass computes and logs but writes nothing."),
                 ("Invariant", "a safety rule the shield enforces before any action."),
                 ("Paired bootstrap CI", "resampling the per-scenario differences to get a 95% interval for the mean difference."),
                 ("Pre-registration", "freezing code and parameters, with hashes, before running the test data.")]:
        w(f"- **{t}**: {d}")
    w("")
    Path(a.out).write_text("\n".join(L))
    print(f"wrote {a.out} ({len(L)} lines)")


if __name__ == "__main__":
    main()
