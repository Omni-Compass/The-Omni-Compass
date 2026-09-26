"""Fleet benchmark: held-out scenarios for every vessel and arm, paired comparisons against HPA+CA and Karpenter-lite.

python -m fleet.benchmark --seeds 30 --seed-base 500000 --out results/fleet
"""
import argparse, csv, json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet.sim import run, arms_for
from fleet.harness import make_scenario

VESSELS = ("web", "multi", "batch", "gpu", "gpu_always_on")
LOWER = ["energy_kwh", "violation_backlog", "violation_power", "violation_heat", "machines_started", "machines_stopped", "node_reversals", "park_moves"]
HIGHER = ["time_healthy", "work_completed"]


def paired(rows, v, base, cand, m, rng):
    A = {r["seed"]: r[m] for r in rows if r["vessel"] == v and r["arm"] == base}
    B = {r["seed"]: r[m] for r in rows if r["vessel"] == v and r["arm"] == cand}
    d = np.array([B[k] - A[k] for k in sorted(A)], float)
    bs = d[rng.integers(0, len(d), (4000, len(d)))].mean(axis=1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    lower = m in LOWER
    verdict = ("better" if (hi < 0) == lower else "worse") if (hi < 0 or lo > 0) else "not significant"
    return {"metric": m, "base": float(np.mean(list(A.values()))), "cand": float(np.mean(list(B.values()))),
            "delta": float(d.mean()), "ci95": [float(lo), float(hi)], "verdict": verdict}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=30); ap.add_argument("--seed-base", type=int, required=True)
    ap.add_argument("--out", required=True); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows = []
    for v in VESSELS:
        for s in range(a.seed_base, a.seed_base + a.seeds):
            scn = make_scenario(v, s)
            for arm in arms_for(v):
                r = run(scn, arm); rows.append({k: (float(x) if isinstance(x, (np.floating,)) else x) for k, x in r.items()})
    with open(out / "RUNS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    rng = np.random.default_rng(12345)
    summ = {"seeds": a.seeds, "seed_base": a.seed_base, "vessels": {}}
    for v in VESSELS:
        arms = arms_for(v)
        means = {arm: {m: float(np.mean([r[m] for r in rows if r["vessel"] == v and r["arm"] == arm])) for m in LOWER + HIGHER} for arm in arms}
        obs = sum(r1["trace_hash"] == r2["trace_hash"] for r1 in rows if r1["vessel"] == v and r1["arm"] == "k8s_hpa70_ca"
                  for r2 in rows if r2["vessel"] == v and r2["arm"] == "omni_observe" and r2["seed"] == r1["seed"])
        comps = {}
        for base in ("k8s_hpa70_ca", "k8s_hpa70_karpenter"):
            for cand in [x for x in arms if x.startswith("omni") and x != "omni_observe"]:
                comps[f"{cand}_vs_{base}"] = [paired(rows, v, base, cand, m, rng) for m in LOWER + HIGHER]
        for abl in ("omni_fleet_no_dynamics", "omni_fleet_no_gate"):
            comps[f"omni_fleet_vs_{abl}"] = [paired(rows, v, abl, "omni_fleet", m, rng) for m in LOWER + HIGHER]
        summ["vessels"][v] = {"means": means, "paired": comps, "observe_identical_to_hpa70_ca": obs, "scenarios": a.seeds}
    (out / "SUMMARY.json").write_text(json.dumps(summ, indent=2))
    for v in VESSELS:
        M = summ["vessels"][v]["means"]
        print(v, "observe identical", summ["vessels"][v]["observe_identical_to_hpa70_ca"], "/", a.seeds)
        for arm in arms_for(v):
            print("  ", arm.ljust(24), {m: round(M[arm][m], 3) for m in ("energy_kwh", "time_healthy", "work_completed", "violation_backlog", "node_reversals", "machines_started")})


if __name__ == "__main__":
    main()
