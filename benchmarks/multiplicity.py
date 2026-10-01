"""Primary-endpoint and multiplicity analysis of the held-out comparison.

Primary comparison: omni_k8s_throughput vs k8s_ref_70. Primary metric: energy_kwh.
Secondary metrics are tested with a paired sign-flip permutation test (two-sided, 10,000 permutations per test,
seeded) and Holm-Bonferroni adjusted across all secondary metrics and both held-out seeds together.
"""
import csv, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = "energy_kwh"
SECONDARY = [("time_healthy", False), ("recovery_minutes", True), ("recovered", False), ("sla_violation_physical", True),
             ("violation_backlog", True), ("violation_power", True), ("violation_heat", True), ("availability", False),
             ("invariant_violations_ex_power", True), ("scale_reversals", True), ("machine_round_trips", True),
             ("thermal_travel", True)]
BASE, CAND, PERMS = "k8s_ref_70", "omni_k8s_throughput", 10000


def diffs(sd, metric):
    rows = list(csv.DictReader(open(ROOT / "results" / f"heldout_seed_{sd}" / "RUNS.csv")))
    a = {r["scenario_id"]: float(r[metric]) for r in rows if r["arm"] == BASE}
    b = {r["scenario_id"]: float(r[metric]) for r in rows if r["arm"] == CAND}
    return np.array([b[k] - a[k] for k in sorted(a)])


def perm_p(d, rng):
    obs = abs(d.mean())
    if np.all(d == 0):
        return 1.0
    signs = rng.choice([-1.0, 1.0], size=(PERMS, len(d)))
    null = np.abs((signs * d).mean(axis=1))
    return float((1 + np.sum(null >= obs - 1e-15)) / (PERMS + 1))


def main(out=ROOT / "results" / "MULTIPLICITY.json"):
    seeds = json.loads((ROOT / "results" / "PREREGISTRATION.json").read_text())["held_out_seeds"]
    rng = np.random.default_rng(20260924)
    res = {"primary": {}, "secondary": [], "method": __doc__.strip()}
    for sd in seeds:
        d = diffs(sd, PRIMARY)
        res["primary"][str(sd)] = {"metric": PRIMARY, "mean_delta": float(d.mean()), "p": perm_p(d, rng), "better": int((d < 0).sum()), "n": len(d)}
    tests = []
    for sd in seeds:
        for m, lower in SECONDARY:
            d = diffs(sd, m)
            tests.append({"seed": sd, "metric": m, "mean_delta": float(d.mean()), "p": perm_p(d, rng),
                          "direction": ("better" if (d.mean() < 0) == lower else "worse") if d.mean() != 0 else "none"})
    order = sorted(range(len(tests)), key=lambda i: tests[i]["p"])
    k = len(tests); running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (k - rank) * tests[i]["p"]))
        tests[i]["p_holm"] = running
        tests[i]["verdict"] = tests[i]["direction"] if running < 0.05 else "not significant"
    res["secondary"] = tests
    Path(out).write_text(json.dumps(res, indent=2))
    for sd, r in res["primary"].items():
        print(f"primary seed {sd}: energy delta {r['mean_delta']:+.2f} kWh, p = {r['p']:.1e}, better in {r['better']}/{r['n']}")
    for t in tests:
        print(f"  {t['seed']} {t['metric']:30s} {t['mean_delta']:+9.4f}  p_holm {t['p_holm']:.1e}  {t['verdict']}")


if __name__ == "__main__":
    main()
