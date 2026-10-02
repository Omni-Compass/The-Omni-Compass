# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Three columns, same scenarios: A Kubernetes alone, B Omni-Compass on top of Kubernetes, C Omni-Compass alone.
Held-out seeds 700201-700230 per workload. Writes results/ABC_TABLE.json and prints the table."""
import json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import BLaw
from tuning.speed_search import gauges
from tuning.league import candidates, run_arm

B_SET = json.load(open(ROOT / "tuning/B_SETTINGS_PER_PLATFORM.json"))
C_PICK = json.load(open(ROOT / "tuning/LEAGUE_HELDOUT.json"))["omni_per_vessel"]
CANDS = candidates()
SEEDS = list(range(700201, 700231))


def job(a):
    v, s = a
    sc = make_scenario(v, s)
    return v, s, {"A": gauges(sim_slo.run(sc, "k8s_hpa70_ca")),
                  "B": gauges(sim_slo.run(sc, "omniB:k8s_hpa70_ca", b_law=BLaw(**B_SET[v]["k8s_hpa70_ca"]))),
                  "C": run_arm(sc, C_PICK[v], CANDS[C_PICK[v]])}


if __name__ == "__main__":
    with Pool(4) as p:
        res = p.map(job, [(v, s) for v in ("web", "multi", "batch", "gpu") for s in SEEDS])
    out = {}
    for v in ("web", "multi", "batch", "gpu"):
        rows = [r for vv, s, r in res if vv == v]
        out[v] = {arm: {m: float(np.mean([r[arm][m] for r in rows])) for m in rows[0]["A"] if isinstance(rows[0]["A"][m], (int, float))}
                  for arm in "ABC"}
    (ROOT / "results/ABC_TABLE.json").write_text(json.dumps(out, indent=1))
    for v, d in out.items():
        print(v)
        for m in ("energy_kwh", "node_hours", "p95_ms", "p99_ms", "mean_ms", "start_stop", "node_reversals", "work_completed", "time_healthy"):
            print(f"  {m:16} A {d['A'][m]:10.4g}  B {d['B'][m]:10.4g}  C {d['C'][m]:10.4g}")
