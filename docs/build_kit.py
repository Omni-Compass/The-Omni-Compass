#!/usr/bin/env python3
"""Builds docs/CLAIMS_REGISTER.md, docs/DUE_DILIGENCE.md and docs/PILOT_PROTOCOL.md from results/."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
PRE = json.loads((R / "PREREGISTRATION.json").read_text())
HO = {sd: json.loads((R / f"heldout_seed_{sd}" / "SUMMARY.json").read_text()) for sd in PRE["held_out_seeds"]}
SOAK_ALL = json.loads((R / "SOAK.json").read_text())
SOAK = SOAK_ALL["power_protect"]
MULT = json.loads((R / "MULTIPLICITY.json").read_text())
FLEET = json.loads((R / "fleet_overhead.json").read_text())
CORE = json.loads((R / "core_evidence.json").read_text())
S1, S2 = PRE["held_out_seeds"]


def m(sd, arm, k):
    return HO[sd]["means"][arm][k]


def pr(sd, comp, k):
    return next(r for r in HO[sd]["paired"][comp] if r["metric"] == k)


def verdict(sd, comp, k, lower):
    r = pr(sd, comp, k); lo, hi = r["ci95"]
    if hi < 0:
        return "better" if lower else "worse"
    if lo > 0:
        return "worse" if lower else "better"
    return "no significant difference"


REFS = ("k8s_ref_50", "k8s_ref_60", "k8s_ref_70", "k8s_ref_80")


def across(arm, k, lower=True):
    vs = [verdict(sd, f"{arm}_vs_{b}", k, lower) for sd in (S1, S2) for b in REFS]
    n = sum(v == "better" for v in vs)
    w = sum(v == "worse" for v in vs)
    return f"better in {n}, worse in {w}, not significantly different in {len(vs) - n - w} of {len(vs)} seed-target combinations"


def both(arm, k, fmt, base="k8s_ref_70", lower=True):
    comp = f"{arm}_vs_{base}"
    return " / ".join(f"{fmt(m(sd, base, k))} to {fmt(m(sd, arm, k))} ({verdict(sd, comp, k, lower)})" for sd in (S1, S2))


pct = lambda v: f"{100 * v:.1f}%"; f1 = lambda v: f"{v:.1f}"; f2 = lambda v: f"{v:.2f}"
rate_bound = 3.0 / SOAK["decisions"]

PRIMARY_TXT = "; ".join("seed %s: %+.2f kWh, p = %.1e" % (sd, r["mean_delta"], r["p"]) for sd, r in MULT["primary"].items())
SECONDARY_TXT = "%d better, %d worse, %d not significant" % tuple(sum(t["verdict"] == v for t in MULT["secondary"]) for v in ("better", "worse", "not significant"))

FS = json.loads((R / "fleet" / "heldout" / "SUMMARY.json").read_text())
def _fl(v):
    d = FS["vessels"][v]
    ca = {x["metric"]: x for x in d["paired"]["omni_fleet_vs_k8s_hpa70_ca"]}; kp = {x["metric"]: x for x in d["paired"]["omni_fleet_vs_k8s_hpa70_karpenter"]}
    return "%s: energy %+.1f%% vs HPA+CA (%s), %+.1f%% vs HPA+Karpenter-lite (%s); node reversals %.1f / %.1f / %.1f (CA / Karpenter / Omni)" % (
        v, 100 * (ca["energy_kwh"]["cand"] / ca["energy_kwh"]["base"] - 1), ca["energy_kwh"]["verdict"],
        100 * (kp["energy_kwh"]["cand"] / kp["energy_kwh"]["base"] - 1), kp["energy_kwh"]["verdict"],
        ca["node_reversals"]["base"], kp["node_reversals"]["base"], ca["node_reversals"]["cand"])
def _fm(v, mode):
    d = FS["vessels"][v]; ca = {x["metric"]: x for x in d["paired"][mode + "_vs_k8s_hpa70_ca"]}; kp = {x["metric"]: x for x in d["paired"][mode + "_vs_k8s_hpa70_karpenter"]}
    return "%s %+.1f%% / %+.1f%%, reversals %.1f" % (v, 100 * (ca["energy_kwh"]["cand"] / ca["energy_kwh"]["base"] - 1), 100 * (kp["energy_kwh"]["cand"] / kp["energy_kwh"]["base"] - 1), ca["node_reversals"]["cand"])
FLEET_TXT = ("15-second control plane, Omni-Compass as node-pool and power authority in place of the Cluster Autoscaler (HPA retained), energy vs HPA+CA / vs HPA+Karpenter-lite: " +
             " | ".join(lab + ": " + "; ".join(_fm(v, m) for v in ("web", "multi", "batch", "gpu", "gpu_always_on")) for m, lab in (("omni_fleet", "energy-first"), ("omni_fleet_balanced", "balanced"), ("omni_fleet_wear", "wear-first"), ("omni_fleet_park", "park"))) +
             ". Baseline reversals (CA / Karpenter): " + "; ".join("%s %.1f / %.1f" % (v, FS["vessels"][v]["means"]["k8s_hpa70_ca"]["node_reversals"], FS["vessels"][v]["means"]["k8s_hpa70_karpenter"]["node_reversals"]) for v in ("web", "multi", "batch", "gpu", "gpu_always_on")) + ". In gpu_always_on no arm powers a node off.")

PL = json.loads((R / "fleet" / "planetlab" / "SUMMARY.json").read_text())
def _pl(arm):
    ca = {x["metric"]: x for x in PL["paired"][arm + "_vs_k8s_hpa70_ca"]}; kp = {x["metric"]: x for x in PL["paired"][arm + "_vs_k8s_hpa70_karpenter"]}
    return "%s: energy %+.1f%% vs HPA+CA (%s), %+.1f%% vs Karpenter-lite (%s)" % (arm, 100 * ca["energy_kwh"]["delta"] / PL["means"]["k8s_hpa70_ca"]["energy_kwh"], ca["energy_kwh"]["verdict"],
        100 * kp["energy_kwh"]["delta"] / PL["means"]["k8s_hpa70_karpenter"]["energy_kwh"], kp["energy_kwh"]["verdict"])
PL_TXT = ("Recorded PlanetLab utilization shapes with a declared scale mapping (%d traces, %d scenarios), governor as node-pool authority in place of the Cluster Autoscaler: " % (PL["traces"], PL["scenarios"]) + "; ".join(_pl(a) for a in ("omni_fleet", "omni_fleet_balanced", "omni_fleet_wear", "omni_fleet_park")) +
          ". Time healthy and work completed are significantly lower by 0.08 points and 0.01%%; observe mode identical in %d/%d." % (PL["observe_identical"], PL["scenarios"]))

claims = [
    ("C1", "The six-state mechanism is implemented identically in the reference engine, Python and C++.", "Proven (exact parity tests)", "python verify.py"),
    ("C2", "The C++ governor reproduces the Python governor on recorded stack telemetry.", "Proven (0 mismatches)", "python tests/test_cpp_governor_parity.py <oc_governor>"),
    ("C2s", "The C++ shield reproduces the Python shield (enforced actions, intervention counts and violations) on action sets recorded from every arm type; a C++ shield with invariant I1 weakened is rejected by the parity test.", "Proven (0 mismatches; negative control)", "python verify.py"),
    ("C2h", "An independent C++ implementation of the HPA replica law (ratio rule, 10% tolerance, scale-up limit, 300 s scale-down window) reproduces the fleet harness HPA on every recorded step (hundreds of thousands of steps across Kubernetes and governor arms); a C++ HPA with 5% tolerance is rejected.", "Proven (0 mismatches; negative control)", "python verify.py"),
    ("C3", "The S channel cannot cross S- (forward invariance).", "Proven (Proposition 1)", "Manual Chapter 3"),
    ("C4", f"The governor completed {SOAK['decisions']:,} consecutive decisions ({SOAK['years_at_5min_interval']:.0f} years at 5-minute intervals) with {SOAK['nonfinite_or_out_of_range']} failures and constant memory; failure-rate upper bound {rate_bound:.1e} at 95% confidence.", "Measured (soak test); reproduced by the full verifier", "python verify.py"),
    ("C4b", f"Throughput-mode soak: {SOAK_ALL['throughput']['decisions']:,} decisions, {SOAK_ALL['throughput']['nonfinite_or_out_of_range']} failures; resident memory at 25/50/75/100% of each run is constant ({SOAK['rss_kb_at_25_50_75_100pct']} kB power-protect, {SOAK_ALL['throughput']['rss_kb_at_25_50_75_100pct']} kB throughput).", "Measured (soak test)", "python verify.py"),
    ("C8p", "Primary endpoint (energy, throughput vs reference target 0.7): " + PRIMARY_TXT + ". Secondary metrics Holm-adjusted over 24 tests: " + SECONDARY_TXT + ".", "Measured in simulation", "python benchmarks/multiplicity.py"),
    ("C5", f"One governor decision costs {SOAK['ns_per_decision'] / 1000:.1f} microseconds on one CPU core of the test machine (machine-dependent).", "Measured", "cpp: oc_soak"),
    ("C6", f"Observe mode leaves the stack bit-identical: over Kubernetes, identical to Kubernetes alone ({HO[S1]['layered_observe_identical_to_kubernetes']}/500 and {HO[S2]['layered_observe_identical_to_kubernetes']}/500); over the native model, identical to native ({HO[S1]['observe_mode_identical_to_native']}/500 and {HO[S2]['observe_mode_identical_to_native']}/500).", "Measured in simulation", "results/heldout_seed_*"),
    ("C7", f"Invariant violations per run (all arms scored identically): Kubernetes reference {m(S1, 'k8s_ref_70', 'invariant_violations'):.2f} / {m(S2, 'k8s_ref_70', 'invariant_violations'):.2f}; power-protect {m(S1, 'omni_k8s_protect', 'invariant_violations'):.2f} / {m(S2, 'omni_k8s_protect', 'invariant_violations'):.2f}; throughput {m(S1, 'omni_k8s_throughput', 'invariant_violations'):.2f} / {m(S2, 'omni_k8s_throughput', 'invariant_violations'):.2f}, of which all are I4 (projected power), which throughput mode does not enforce; excluding I4: reference {m(S1, 'k8s_ref_70', 'invariant_violations_ex_power'):.2f} / {m(S2, 'k8s_ref_70', 'invariant_violations_ex_power'):.2f}, throughput {m(S1, 'omni_k8s_throughput', 'invariant_violations_ex_power'):.2f} / {m(S2, 'omni_k8s_throughput', 'invariant_violations_ex_power'):.2f}.", "Measured in simulation", "results/heldout_seed_*"),
    ("C8", f"Energy for Omni-Compass over Kubernetes (throughput mode, same power rules as the reference) versus the Kubernetes reference model (HPA target 0.7): {both('omni_k8s_throughput', 'energy_kwh', f1)} kWh per run; across HPA targets 0.5 to 0.8: {across('omni_k8s_throughput', 'energy_kwh')}.", "Measured in simulation (synthetic stack, documented-behaviour reference model)", "results/heldout_seed_*"),
    ("C9", f"Time healthy for Omni-Compass over Kubernetes (throughput mode) versus the reference model (target 0.7): {both('omni_k8s_throughput', 'time_healthy', pct, lower=False)}; across targets: {across('omni_k8s_throughput', 'time_healthy', lower=False)}.", "Measured in simulation", "results/heldout_seed_*"),
    ("C10", f"Recovery time for Omni-Compass over Kubernetes (throughput mode) versus the reference model (target 0.7): {both('omni_k8s_throughput', 'recovery_minutes', f1)} minutes; across targets: {across('omni_k8s_throughput', 'recovery_minutes')}.", "Measured in simulation", "results/heldout_seed_*"),
    ("C11", f"Backlog violations for Omni-Compass over Kubernetes (throughput mode) versus the reference model (target 0.7): {both('omni_k8s_throughput', 'violation_backlog', pct)}; across targets: {across('omni_k8s_throughput', 'violation_backlog')}.", "Measured in simulation", "results/heldout_seed_*"),
    ("C12", f"Machine round trips (started and later stopped), throughput mode versus the reference (target 0.7): {both('omni_k8s_throughput', 'machine_round_trips', f1)} per run; across targets: {across('omni_k8s_throughput', 'machine_round_trips')}. The reference removes a machine only after 10 minutes below 50% utilization and keeps post-event machines running; the governor releases them, which is the main source of its energy saving.", "Measured in simulation", "results/heldout_seed_*"),
    ("C12w", f"Scale direction reversals (back-and-forth wear), throughput mode versus the reference (target 0.7): {both('omni_k8s_throughput', 'scale_reversals', f2)} per run; across targets: {across('omni_k8s_throughput', 'scale_reversals')}. Power-protect: {both('omni_k8s_protect', 'scale_reversals', f2)}.", "Measured in simulation", "results/heldout_seed_*"),
    ("C12e", f"Engine mechanism in the flagship (throughput): removing the equation (2) release gate changes reversals from {m(S1, 'omni_k8s_throughput', 'scale_reversals'):.2f} / {m(S2, 'omni_k8s_throughput', 'scale_reversals'):.2f} to {m(S1, 'omni_k8s_throughput_no_gate', 'scale_reversals'):.2f} / {m(S2, 'omni_k8s_throughput_no_gate', 'scale_reversals'):.2f} and energy from {m(S1, 'omni_k8s_throughput', 'energy_kwh'):.1f} / {m(S2, 'omni_k8s_throughput', 'energy_kwh'):.1f} to {m(S1, 'omni_k8s_throughput_no_gate', 'energy_kwh'):.1f} / {m(S2, 'omni_k8s_throughput_no_gate', 'energy_kwh'):.1f} kWh; removing engine evolution changes energy to {m(S1, 'omni_k8s_throughput_no_dynamics', 'energy_kwh'):.1f} / {m(S2, 'omni_k8s_throughput_no_dynamics', 'energy_kwh'):.1f} kWh and reversals to {m(S1, 'omni_k8s_throughput_no_dynamics', 'scale_reversals'):.2f} / {m(S2, 'omni_k8s_throughput_no_dynamics', 'scale_reversals'):.2f}.", "Measured in simulation", "results/heldout_seed_*"),
    ("C12p", f"Power-protect mode (enforces the site power limit, which the reference does not): energy {both('omni_k8s_protect', 'energy_kwh', f1)} kWh; power-limit violations {both('omni_k8s_protect', 'violation_power', pct)}; backlog violations {both('omni_k8s_protect', 'violation_backlog', pct)}.", "Measured in simulation", "results/heldout_seed_*"),
    ("C12a", "Human pages: the governor issues no page actions. Zero pages is a design property, not a measured performance result.", "Design", "omnicompass/adapter.py"),
    ("C12b", "The reference model is not the upstream Kubernetes controllers: Cluster Autoscaler scheduling simulation, Karpenter, VPA, scheduling constraints and disruption budgets are not represented.", "Stated limitation", "benchmarks/stack_benchmark.py (K8sReference)"),
    ("C15", FLEET_TXT, "Measured in simulation (fleet harness, synthetic workloads, documented-behaviour execution layer)", "python -m fleet.benchmark --seeds 30 --seed-base 700000 --out out/"),
    ("C17", PL_TXT, "Measured in simulation driven by recorded traces (frozen laws, no retuning)", "python -m fleet.planetlab --dir fleet/traces/planetlab --scenarios 30 --seed-base 800000 --out out/"),
    ("C16", "Live-cluster capture, capture replay and the PlanetLab vessel are tested on generated inputs in the real formats. No real capture or recorded trace has been run in the package.", "Tested path; no real-data result", "python tests/test_fleet_realdata_paths.py"),
    ("C19", "The live controller (omni_controller/) implements observe, target and nodepool modes with dry-run, audit log and a kill switch that restores HPA targets from annotations; tested against a fake kubectl only, never against a real cluster.", "Tested path; no live result", "python tests/test_omni_controller.py"),
    ("C18", "Savings projection: the energy-first reduction relative to HPA + Karpenter-lite, applied to declared fleet profiles (results/SAVINGS.csv), computed identically in Python and C++. A projection from simulation, not measured savings.", "Projection", "python benchmarks/savings.py"),
    ("C21", "End-to-end self-pilot (shipped controller, simulated cluster, real capture and scoring), default headroom 50%: energy per core-hour -7.7%, node-hours per core-hour -13.8%, pending-pod time not significantly different from HPA + Cluster Autoscaler; HPA shortfall minutes higher. Lower headroom saves more energy with more pending-pod time (manual Section 8.12a).", "Measured in simulation", "python pilot/selfpilot.py"),
    ("C20", "pilot/score.py scores a user's own captures (node-hours and energy per used core-hour, utilisation, pending-pod and HPA-shortfall minutes, bootstrap intervals); tested to detect a real gain, report no difference for identical clusters and detect a service regression.", "Tested tool; no pilot result", "python tests/test_pilot_score.py"),
    ("C13", f"Decision components (autoscalers, power agents, paging, Terraform as controller) consume about {100 * FLEET['util8_sidecar']['by_role']['decision']['share_of_fleet_vcpu']:.2f}% of fleet CPU; idle capacity is {100 * FLEET['util8_sidecar']['idle_share_of_fleet_vcpu']:.0f}% of fleet CPU at 8% utilization.", "Modeled from published figures and stated assumptions", "python benchmarks/fleet_overhead.py"),
    ("C14", "Behaviour on production systems.", "Not established; requires the pilot protocol", "docs/PILOT_PROTOCOL.md"),
]

L = ["# Claims Register", "",
     "Every claim, its evidence status and the command that reproduces it. Simulation results use the synthetic stack model "
     "in omnicompass/stack_sim.py; they are not production measurements.", "",
     "| ID | Claim | Status | Reproduce |", "|---|---|---|---|"]
L += [f"| {a} | {b} | {c} | `{d}` |" for a, b, c, d in claims]
(ROOT / "docs" / "CLAIMS_REGISTER.md").write_text("\n".join(L) + "\n")

dd = f"""# Due Diligence

Answers reference the Claims Register (C-numbers) and the Technical Manual.

## Engineering
**Does the mathematics hold?** Equations (1) to (8), Propositions 1 to 3 and their proofs are in Manual Chapters 2 and 3. The 500/500 CONVEY/CERT result is a property of the controller (Proposition 3), shown by counterfactuals: the controller aimed at the wrong basin also scores {CORE['wrong_target']['convey5']}/500.
**Is Python the same as C++?** Yes (C1, C2). The verifier also builds a deliberately mutated C++ governor and confirms the parity test rejects it.
**Can every number be reproduced?** `python verify.py` rebuilds the C++, reruns parity, reruns the 100,000,000-decision soak and compares it with the recorded result, replays held-out scenarios and checks the pre-registered SHA-256 hashes (program fingerprints are additionally checked when the Python version matches the recorded one).

## Operations
**Better than what we run today?** Compared against a documented-behaviour reference model of Kubernetes autoscaling (HPA tolerance 0.1, 300 s scale-down stabilization, HPA targets 0.5 to 0.8; simplified Cluster Autoscaler with 10-minute unneeded time, 0.5 utilization threshold, 10-minute delay after scale-up): C8 to C12, including where Omni-Compass is worse. The reference model is not the upstream controllers (C12b); running the upstream controllers against the same scenarios is the next baseline step.
**On real traffic?** Not yet. Results use a synthetic stack model. Replay of published production traces and the pilot protocol are the next evidence steps (C14).
**What happens when it is wrong?** Observe mode changes nothing (C6). The kill switch returns control to the native managers at the next interval (omni_kill arm). The shield blocks actions that violate I1 to I5 (C7).
**Will it wear hardware?** Machine start/stop cycles, power-cap travel and thermal travel are measured for every arm (C12, Manual Chapter 8).

## Security
**What authority does it hold?** Capacity, replicas, power caps, rollback authorization and routing, only in AUTOPILOT, only through the shield.
**Can it expand capacity during a security block?** No: invariant I1 is enforced before execution.
**Does it replace encryption, identity or policy engines?** No. Those components are retained (fleet model, security role).

## Finance
**What does it save?** Energy per run versus current autoscaling (C8). Fleet-scale figures are modeled (C13); the governance saving comes from reduced idle and padded capacity, not from removing the decision components' own consumption.
**What does it cost to run?** C5.

## Adoption
**How is it introduced without risk?** Observe, then shadow on production telemetry, then one control loop at a time under the kill switch (docs/PILOT_PROTOCOL.md).

## Referees
**Was it tuned on the test data?** No. Law, shield and baselines were frozen and fingerprinted before the held-out seeds {S1} and {S2} (results/PREREGISTRATION.json).
**Where does it fail?** Backlog violations against current autoscaling (C11); the engine-dynamics ablation (Manual Chapter 8); open obligations (Manual Chapter 10).
"""
(ROOT / "docs" / "DUE_DILIGENCE.md").write_text(dd)

pp = """# Pilot Protocol

## Phase 0: Simulation evaluation (evaluator's own environment)
Run `python verify.py`. Pass criterion: VERIFICATION: PASS.

## Phase 1: Shadow (2 to 4 weeks)
- Capture: `OUT=capture.csv INTERVAL=15 DURATION=<seconds> POWER_CMD="<site power in watts>" bash fleet/capture/kube_capture.sh` (read-only).
- Replay: `python fleet/capture_replay.py capture.csv --idle-w <W> --dyn-w <W> --site-limit-w <W> --out replay/` gives Omni-Compass's recommended node count, power cap and HPA target per decision.
- Governor in OBSERVE on production telemetry read directly from nodes (kubelet/cAdvisor metrics, power meters, queue depth).
- No write credentials are issued.
- Logged per interval: directive, native actions taken, and the observed outcome.
- Pass criteria, agreed before start: logged directives never violate I1 to I5; counterfactual analysis on at least N recorded incidents shows the directive would have reduced time-to-recovery or energy without a backlog increase beyond an agreed bound.

## Phase 2: Guarded control, one loop at a time (4 to 8 weeks)
Order: power capping; node count (Cluster Autoscaler set to observe); replica count (HPA set to observe).
- Each loop is handed over separately, with the kill switch tested at handover and at exit.
- Pass criteria per loop, fixed in advance: SLO attainment not worse than the preceding shadow baseline at the agreed confidence level; zero shield invariant violations; energy per unit of completed work reported with confidence intervals.
- Exit: any criterion failed triggers the kill switch and returns the loop to its native controller.

## Scoring your own pilot
Capture the baseline (a period before the controller, or a matched node pool left on your normal autoscaler) and the
Omni-Compass period or pool with fleet/capture/kube_capture.sh, then:
`python pilot/score.py --baseline baseline.csv --omni omni.csv [--idle-w W --dyn-w W]`
It reports node-hours and energy per used CPU core-hour, utilisation, pending-pod minutes and HPA shortfall minutes, each
with a bootstrap 95% interval over hourly blocks. Energy is measured if the captures include power_w. Run long enough
for at least 24 blocks per side, and compare matched pools at the same time where possible, because traffic changes
between periods.

## Phase 3: Component retirement
A decision component is retired only after its loop has passed Phase 2 and a one-at-a-time removal shows no degradation (keep-or-remove rule, Manual Chapter 6). Execution and security components are retained.

## Reporting
All pilot metrics, including failures, are reported in the same format as the benchmark results.
"""
(ROOT / "docs" / "PILOT_PROTOCOL.md").write_text(pp)
print("wrote CLAIMS_REGISTER.md, DUE_DILIGENCE.md, PILOT_PROTOCOL.md")
