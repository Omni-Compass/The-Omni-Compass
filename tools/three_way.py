# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Three columns: Kubernetes alone (HPA 70% + Cluster Autoscaler) | Omni-Compass on top of it (B) | Omni-Compass alone (C),
on fresh scenarios never used before (seeds 713001-713030 per workload), every gauge, paired bootstrap vs Kubernetes.
Settings are all frozen before this run: B = tuning/B_SETTINGS_TONE.json (Kubernetes column), C = the global setting
of tuning/GLOBAL_LEAGUE_PREREGISTRATION.json with the nervous-system coordination on (tuning/COORD_PREREGISTRATION.json).
THEORETICAL SIMULATION (fleet/sim_slo.py). Usage: python tools/three_way.py  ->  results/THREE_WAY.md, results/THREE_WAY.json"""
import json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import DirectLaw, BLaw
from omnicompass.speed import SpeedLaw
from omnicompass.closure import ClosureLaw
from tuning.speed_search import gauges
from tuning.league import VESSELS, LOWER, HIGHER

K8S = "k8s_hpa70_ca"
C2 = "--c2" in sys.argv
SEEDS = list(range(714001, 714031)) if C2 else list(range(713001, 713031))
TONE = json.load(open(ROOT / "tuning/B_SETTINGS_TONE.json"))
SET = json.load(open(ROOT / ("tuning/C2_PREREGISTRATION.json" if "--c2" in sys.argv else "tuning/GLOBAL_LEAGUE_PREREGISTRATION.json")))["setting"]
NAMES = {"energy_kwh": "Energy (kWh)", "node_hours": "Machine-hours", "p95_ms": "Response time p95 (ms)",
         "p99_ms": "Response time p99 (ms)", "mean_ms": "Response time mean (ms)", "violation_backlog": "Time over backlog limit",
         "violation_power": "Time over power limit", "violation_heat": "Time over heat limit", "start_stop": "Machine starts+stops",
         "node_reversals": "Scale reversals", "pod_changes": "Pod changes", "work_completed": "Work completed",
         "time_healthy": "Time healthy", "contradictions": "Controllers fighting (per day)"}


def job(a):
    v, s = a
    sc = make_scenario(v, s)
    r0 = sim_slo.run(sc, K8S)
    rb = sim_slo.run(sc, "omniB:" + K8S, b_law=BLaw(**TONE[v][K8S]))
    cl = dict(SET["closure"], site=(v == "multi"), coord=True)
    rc = sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**SET["speed"]), omni_every=1,
                     direct_law=DirectLaw(**SET["direct"]), closure_law=ClosureLaw(**cl))
    out = []
    for r in (r0, rb, rc):
        g = gauges(r); g["contradictions"] = r.get("contradictions", 0); out.append(g)
    return (v, s), out


def main():
    with Pool(4) as p:
        res = dict(p.map(job, [(v, s) for v in VESSELS for s in SEEDS], chunksize=2))
    rng = np.random.default_rng(20260927)
    keys = [k for k in NAMES if k in res[(VESSELS[0], SEEDS[0])][0]]
    out = {"seeds": [SEEDS[0], SEEDS[-1]], "workloads": {}}
    L = ["# Three columns: Kubernetes alone | Omni-Compass on top | Omni-Compass alone", "",
         f"Fresh scenarios {SEEDS[0]}-{SEEDS[-1]} (30 per workload, never used before). THEORETICAL SIMULATION (fleet/sim_slo.py).",
         "Settings frozen before the run. Marks: **better** / *worse* = paired 95% interval vs Kubernetes excludes 0 "
         "and the difference is over 0.5%; otherwise equal.", ""]
    for v in VESSELS:
        L += [f"## {v}", "", "| Gauge | Kubernetes alone | Omni on top | Omni alone |", "|---|---:|---:|---:|"]
        out["workloads"][v] = {}
        for k in keys:
            cols = [np.array([res[(v, s)][i][k] for s in SEEDS], float) for i in range(3)]
            cells = [f"{cols[0].mean():.4g}"]
            rec = {"k8s": float(cols[0].mean())}
            for i, name in ((1, "on_top"), (2, "alone")):
                d = cols[i] - cols[0]
                bs = d[rng.integers(0, len(d), (5000, len(d)))].mean(1); lo, hi = np.percentile(bs, [2.5, 97.5])
                low_better = k not in HIGHER and k not in ("work_completed", "time_healthy")
                pct = 100 * d.mean() / max(abs(cols[0].mean()), 1e-9)
                sig = (lo > 0 or hi < 0) and abs(pct) > 0.5
                better = (d.mean() < 0) == low_better
                mark = ("**better**" if better else "*worse*") if sig else "equal"
                cells.append(f"{cols[i].mean():.4g} ({pct:+.0f}%, {mark})")
                rec[name] = {"mean": float(cols[i].mean()), "pct": float(pct), "verdict": mark.strip("*")}
            out["workloads"][v][k] = rec
            L.append(f"| {NAMES[k]} | " + " | ".join(cells) + " |")
        L.append("")
    tally = {c: {"better": 0, "equal": 0, "worse": 0} for c in ("on_top", "alone")}
    for v in out["workloads"].values():
        for rec in v.values():
            for c in tally:
                tally[c][rec[c]["verdict"]] += 1
    out["tally"] = tally
    L += ["## Tally across all workloads and gauges", "", "| | better | equal | worse |", "|---|---:|---:|---:|",
          f"| Omni on top | {tally['on_top']['better']} | {tally['on_top']['equal']} | {tally['on_top']['worse']} |",
          f"| Omni alone | {tally['alone']['better']} | {tally['alone']['equal']} | {tally['alone']['worse']} |"]
    tag = "_C2" if C2 else ""
    if C2:
        L[0] += " (Omni alone v2, frozen in tuning/C2_PREREGISTRATION.json)"
    (ROOT / f"results/THREE_WAY{tag}.md").write_text("\n".join(L) + "\n"); (ROOT / f"results/THREE_WAY{tag}.json").write_text(json.dumps(out, indent=1))
    print("\n".join(L))


if __name__ == "__main__":
    main()
