# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The self-calibrating closure law (omnicompass/closure.py AutoClosureLaw) against all seven platforms. No setting is
tuned per workload: the law derives its horizons from the boot delay and the park break-even, its margin from the
measured forecast error and the engine's stress, and packs to the physical boundary. The only global choice is the pod
rule (declared here, the same for every workload). Multi-cluster sites run the law on the site total with traffic shift.
Usage: python tuning/auto_league.py dev|heldout  ->  tuning/AUTO_LEAGUE_{DEV,HELDOUT}.json"""
import json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import DirectLaw
from omnicompass.speed import SpeedLaw
from omnicompass.closure import AutoClosureLaw
from tuning.speed_search import gauges
from tuning.league import COMPETITORS, VESSELS, LOWER, HIGHER, losses

POD_RULES = {"hpa70": (dict(rho0=0.7, rho_min=0.7, kI=0.0, kE=0.0), dict(window=40, kb=1.0, push_release=0.2, tol=0.1)),
             "staff10": (dict(rho0=0.7, rho_min=0.7, kI=0.0, kE=0.0), dict(window=40, kb=1.0, push_release=0.2, tol=0.1, wq=0.1))}
SEEDS = {"dev": list(range(101, 131)), "heldout": list(range(702001, 702031))}


def omni(sc, v, rule):
    sl, dl = POD_RULES[rule]
    return gauges(sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**sl), omni_every=1, direct_law=DirectLaw(**dl),
                              closure_law=AutoClosureLaw(site=(v == "multi"))))


def job(a):
    v, s, rules = a
    sc = make_scenario(v, s)
    row = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    for r in rules:
        row["omni_" + r] = omni(sc, v, r)
    return (v, s), row


if __name__ == "__main__":
    which = sys.argv[1]
    rules = list(POD_RULES) if which == "dev" else [json.load(open(ROOT / "tuning/AUTO_LEAGUE_DEV.json"))["pod_rule"]]
    seeds = SEEDS[which]
    with Pool(4) as p:
        rows = dict(p.map(job, [(v, s, rules) for v in VESSELS for s in seeds], chunksize=1))
    out = {"seeds": seeds, "rules": rules, "cells": {}, "means": {}}
    for r in rules:
        rng = np.random.default_rng(11)
        L = [l for v in VESSELS for c in COMPETITORS for l in losses(rows, seeds, "omni_" + r, c, v, rng)]
        out["cells"][r] = L
        out["means"][r] = {v: {a: {m: float(np.mean([rows[(v, s)][a][m] for s in seeds])) for m in LOWER + HIGHER}
                               for a in COMPETITORS + ["omni_" + r]} for v in VESSELS}
        print(r, "losing cells", len(L), "of", 13 * 7 * 4, flush=True)
        for v in VESSELS:
            print("  ", v, [(l["competitor"], l["gauge"], round(l["omni_worse_by_pct"], 1)) for l in L if l["vessel"] == v], flush=True)
    if which == "dev":
        out["pod_rule"] = min(rules, key=lambda r: len(out["cells"][r]))
    (ROOT / f"tuning/AUTO_LEAGUE_{which.upper()}.json").write_text(json.dumps(out, indent=1))
