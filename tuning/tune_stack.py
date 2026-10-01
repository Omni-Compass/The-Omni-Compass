"""Tune allocation-law variants that remove the negatives of the pre-registered stack benchmark, on DEVELOPMENT seeds only.

The frozen engine files are not edited (verify.py fingerprints them). Variants are law overrides applied on top of the
frozen modes:
  B  (omni_k8s_throughput, Omni on top of Kubernetes): overrides applied after the throughput mode
  C  (omni_direct, Omni direct):                        overrides applied to the base law
Objective, against k8s_ref_70 on the same scenarios: energy at least 10% lower, time healthy not lower, and as few
gauges worse than Kubernetes as possible (wear, queue, node-hours, reversals first). Development seeds 1000 and 2000 are
the seeds the original constants were selected on; held-out seeds are never touched here.

python tuning/tune_stack.py --scenarios 60 --out tuning/SEARCH.json
"""
from __future__ import annotations

import argparse, itertools, json, sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import benchmarks.stack_benchmark as sb
from omnicompass import stack_sim as S
from omnicompass.adapter import AllocationLaw, mode_law as frozen_mode_law

DEV_SEEDS = (1000, 2000)
LOWER = ["energy_kwh", "node_start_stop", "machine_round_trips", "scale_reversals", "node_hours", "idle_node_hours",
         "mean_queue", "p95_queue", "violation_backlog", "recovery_minutes", "power_cap_travel", "invariant_violations",
         "sla_violation_total", "pages"]
HIGHER = ["time_healthy", "availability", "recovered"]
PRIORITY = {"node_start_stop", "machine_round_trips", "scale_reversals", "mean_queue", "p95_queue", "node_hours",
            "idle_node_hours", "violation_backlog", "availability"}


def scenarios(n, seed):
    cfg = S.ManagerBenchmarkConfig(profile="full", scenarios=n, steps=72)
    return cfg, S._mom_generate_scenarios(cfg, seed)[:n]


def run_arm(arm, over, cfg, scns):
    base = AllocationLaw()
    if arm == "omni_direct_throughput":
        sb.mode_law = frozen_mode_law
        law = replace(frozen_mode_law("throughput", base), **over)
        try:
            return [sb.simulate(s, "omni_direct", cfg, law) for s in scns]
        finally:
            sb.mode_law = frozen_mode_law
    if arm == "omni_k8s_throughput":
        sb.mode_law = lambda m, law: replace(frozen_mode_law(m, law), **over)
        law = base
    else:
        sb.mode_law = frozen_mode_law
        law = replace(base, **over)
    try:
        return [sb.simulate(s, arm, cfg, law) for s in scns]
    finally:
        sb.mode_law = frozen_mode_law


def compare(k8s, cand):
    out = {}
    for m in LOWER + HIGHER:
        a = np.mean([r[m] for r in k8s]); c = np.mean([r[m] for r in cand])
        rel = (c - a) / abs(a) if a else (0.0 if c == 0 else float("inf"))
        worse = (rel > 0.02) if m in LOWER else (rel < -0.002)
        out[m] = {"k8s": float(a), "cand": float(c), "rel": float(rel), "worse": bool(worse)}
    return out


def score(cmp):
    energy = cmp["energy_kwh"]["rel"]
    ok = energy <= -0.10 and not cmp["time_healthy"]["worse"]
    n_worse = sum(1 for v in cmp.values() if v["worse"]); n_pri = sum(1 for k, v in cmp.items() if v["worse"] and k in PRIORITY)
    return (0 if ok else 1, n_pri, n_worse, energy)


GRIDS = {
    # round 2: the cap moves only when the engine has converged (U_gate) and with a small margin; node release held longer
    "omni_k8s_throughput": dict(down_dwell=[20, 30], down_after_add=[3, 8], U_gate=[0.45, 0.7, 0.9], margin=[0.006, 0.05],
                                cap_min=[0.65, 0.8, 0.9], size_at_full_cap=[True, False]),
    # C in throughput mode (the site power envelope is not forced), node release and target utilisation tuned
    "omni_direct_throughput": dict(down_band=[1, 4, 8], down_dwell=[10, 20], down_after_add=[3, 8], U_gate=[0.45, 0.9],
                                   cap_min=[0.65, 0.8, 0.9], rho0=[0.914, 0.85]),
}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--scenarios", type=int, default=60); ap.add_argument("--out", default="tuning/SEARCH.json")
    a = ap.parse_args(argv)
    sets = [scenarios(a.scenarios, s) for s in DEV_SEEDS]
    k8s = [sb.simulate(s, "k8s_ref_70", cfg, AllocationLaw()) for cfg, scns in sets for s in scns]
    result = {"dev_seeds": DEV_SEEDS, "scenarios_per_seed": a.scenarios, "arms": {}}
    for arm, grid in GRIDS.items():
        keys = list(grid); trials = []
        frozen = [r for cfg, scns in sets for r in run_arm(arm, {}, cfg, scns)]
        fc = compare(k8s, frozen)
        for vals in itertools.product(*grid.values()):
            over = dict(zip(keys, vals))
            rows = [r for cfg, scns in sets for r in run_arm(arm, over, cfg, scns)]
            c = compare(k8s, rows)
            trials.append({"overrides": over, "score": list(score(c)), "compare": c})
        trials.sort(key=lambda t: t["score"])
        result["arms"][arm] = {"frozen": {"score": list(score(fc)), "compare": fc}, "best": trials[0], "top5": trials[:5], "trials": len(trials)}
        b = trials[0]
        print(f"== {arm}: {len(trials)} variants; frozen worse gauges {sum(v['worse'] for v in fc.values())}, "
              f"best worse gauges {sum(v['worse'] for v in b['compare'].values())}")
        print("   best overrides:", b["overrides"])
        for m, v in b["compare"].items():
            flag = "WORSE" if v["worse"] else ""
            print(f"   {m:22} k8s {v['k8s']:10.3f}  frozen {fc[m]['cand']:10.3f} ({100 * fc[m]['rel']:+6.1f}%)  "
                  f"tuned {v['cand']:10.3f} ({100 * v['rel']:+6.1f}%) {flag}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
