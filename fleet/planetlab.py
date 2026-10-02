# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""PlanetLab vessel: recorded VM CPU traces (github.com/beloglazov/planetlab-workload-traces, one integer percent per
line, 288 lines = 24 h at 5 min) as workload demand in the 15-second fleet harness, run with the frozen laws.

Each scenario: one cluster of 12 HPA workloads; each workload is assigned a trace file, a CPU request and a peak pod
count drawn from the scenario seed; demand in cores = trace percent / 100 x peak pods x request; a 6-hour window is
taken from the day and each 5-minute sample is held for 20 ticks. The trace shapes are recorded; the mapping from
percent to cores is declared here.

python -m fleet.planetlab --dir /path/to/planetlab-workload-traces/20110303 --scenarios 30 --out out/
"""
import argparse, csv, json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet.harness import Workload, Pool, Cluster, Scenario, STEPS
from fleet.sim import run, arms_for


def load_dir(d):
    files = sorted(p for p in Path(d).iterdir() if p.is_file())
    traces = {}
    for p in files:
        v = [float(x) for x in p.read_text().split() if x.strip()]
        if len(v) >= 72:
            traces[p.name] = np.array(v)
    if not traces:
        raise ValueError(f"no traces in {d}")
    return traces


def make_scenario(traces, seed):
    rng = np.random.default_rng(seed); names = sorted(traces)
    wls, used = [], []
    for i in range(12):
        name = names[int(rng.integers(0, len(names)))]; tr = traces[name]
        start = int(rng.integers(0, len(tr) - 72 + 1)); window = tr[start:start + 72]
        req = float(rng.choice([0.25, 0.5, 1.0, 2.0])); peak = int(rng.integers(4, 30))
        demand = np.repeat(window / 100.0 * peak * req, STEPS // 72)
        w = Workload(f"w{i}", req, 2, peak * 3, demand); w.replicas = max(2, int(np.ceil(demand[0] / (req * 0.7))))
        wls.append(w); used.append({"trace": name, "start_sample": start, "request": req, "peak_pods": peak})
    scn = Scenario("planetlab", seed, [Cluster(wls, Pool(32.0, 0.20, 0.35, 12, 3, 60))], 38.0 * rng.uniform(0.9, 1.1))
    scn.assignment = used
    return scn


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); ap.add_argument("--scenarios", type=int, default=30)
    ap.add_argument("--seed-base", type=int, default=700000); ap.add_argument("--out", default="planetlab_out"); a = ap.parse_args()
    traces = load_dir(a.dir); rows = []
    for s in range(a.seed_base, a.seed_base + a.scenarios):
        scn = make_scenario(traces, s)
        for arm in arms_for("web"):
            r = run(scn, arm); rows.append({k: (float(v) if hasattr(v, "item") else v) for k, v in r.items()})
    means = {arm: {m: float(np.mean([r[m] for r in rows if r["arm"] == arm])) for m in
                   ("energy_kwh", "time_healthy", "work_completed", "violation_backlog", "node_reversals", "machines_started")} for arm in arms_for("web")}
    base = {r["seed"]: r["trace_hash"] for r in rows if r["arm"] == "k8s_hpa70_ca"}
    obs = sum(base[r["seed"]] == r["trace_hash"] for r in rows if r["arm"] == "omni_observe")
    o = Path(a.out); o.mkdir(parents=True, exist_ok=True)
    with open(o / "RUNS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    rng = np.random.default_rng(12345); paired = {}
    for cand in [x for x in arms_for("web") if x.startswith("omni") and x != "omni_observe"]:
        for base in ("k8s_hpa70_ca", "k8s_hpa70_karpenter"):
            res = []
            for m, lower in (("energy_kwh", True), ("time_healthy", False), ("work_completed", False), ("node_reversals", True)):
                A = {r["seed"]: r[m] for r in rows if r["arm"] == base}; B = {r["seed"]: r[m] for r in rows if r["arm"] == cand}
                d = np.array([B[k] - A[k] for k in sorted(A)]); bs = d[rng.integers(0, len(d), (4000, len(d)))].mean(axis=1)
                lo, hi = np.percentile(bs, [2.5, 97.5])
                res.append({"metric": m, "delta": float(d.mean()), "ci95": [float(lo), float(hi)],
                            "verdict": ("better" if (hi < 0) == lower else "worse") if (hi < 0 or lo > 0) else "not significant"})
            paired[f"{cand}_vs_{base}"] = res
    summ = {"trace_dir": str(a.dir), "traces": len(traces), "scenarios": a.scenarios, "seed_base": a.seed_base, "means": means,
            "observe_identical": obs, "paired": paired}
    (o / "SUMMARY.json").write_text(json.dumps(summ, indent=2)); print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
