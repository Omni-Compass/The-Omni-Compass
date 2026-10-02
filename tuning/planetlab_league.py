# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Real demand: recorded PlanetLab VM CPU traces (github.com/beloglazov/planetlab-workload-traces, day 20110303, 1,052
machines) as web-service demand (fleet/planetlab.py), Omni-Compass alone with the frozen web closure-law setting
(tuning/CLOSURE_FINAL_DEV.json, never tuned on these traces) against the seven platforms, league loss rule, 30 scenarios.
Also runs the same comparison with whole-pod packing (fleet/sim_slo.py PACKING = "bins").
Usage: python tuning/planetlab_league.py /path/to/20110303  ->  tuning/PLANETLAB_LEAGUE.json"""
import json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet import planetlab as PL
from fleet.sim_slo import DirectLaw
from omnicompass.speed import SpeedLaw
from omnicompass.closure import ClosureLaw
from tuning.speed_search import gauges
from tuning.league import COMPETITORS, LOWER, HIGHER, losses

F = json.load(open(ROOT / "tuning/CLOSURE_FINAL_DEV.json"))["web"]
SEEDS = list(range(704001, 704031))
TR = None


def job(a):
    s, packing = a
    sim_slo.PACKING = packing
    sc = PL.make_scenario(TR, s)
    row = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    row["omni"] = gauges(sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**F["speed"]), omni_every=1,
                                     direct_law=DirectLaw(**F["direct"]), closure_law=ClosureLaw(**F["closure"])))
    return s, row


def init(d):
    global TR
    TR = PL.load_dir(d)


if __name__ == "__main__":
    out = {"trace_dir": "planetlab-workload-traces/20110303", "seeds": SEEDS}
    for packing in ("fluid", "bins"):
        with Pool(4, initializer=init, initargs=(sys.argv[1],)) as p:
            rows = dict(p.map(job, [(s, packing) for s in SEEDS], chunksize=1))
        rows2 = {("planetlab", s): r for s, r in rows.items()}
        rng = np.random.default_rng(11)
        L = [l for c in COMPETITORS for l in losses(rows2, SEEDS, "omni", c, "planetlab", rng)]
        means = {a: {m: float(np.mean([rows[s][a][m] for s in SEEDS])) for m in LOWER + HIGHER} for a in COMPETITORS + ["omni"]}
        out[packing] = {"losing_cells": L, "means": means}
        k = means["k8s_hpa70_ca"]; o = means["omni"]
        print(packing, "losing cells", len(L), "of 91:", [(l["competitor"], l["gauge"], round(l["omni_worse_by_pct"], 1)) for l in L], flush=True)
        print("   vs Kubernetes:", {m: f"{(k[m] - o[m]) / abs(k[m]) * 100:+.0f}%" for m in ("energy_kwh", "node_hours", "p95_ms", "p99_ms", "mean_ms", "start_stop")}, flush=True)
    (ROOT / "tuning/PLANETLAB_LEAGUE.json").write_text(json.dumps(out, indent=1))
