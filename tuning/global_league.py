# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""One global closure-law setting for every workload (no per-workload table). Candidates: each workload's frozen
setting from tuning/CLOSURE_FINAL_DEV.json applied to all four workloads (pods at 0.8 for services; job workloads have no
pods to size). Four-cluster sites run the same law on the site total with traffic shift. Selection on 30 development
seeds (101-130) by total losing cells against the seven platforms; the pick is frozen by SHA-256 and run once on fresh
held-out seeds 703001-703030. Usage: python tuning/global_league.py  ->  tuning/GLOBAL_LEAGUE.json"""
import hashlib, json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import DirectLaw
from omnicompass.speed import SpeedLaw
from omnicompass.closure import ClosureLaw
from tuning.speed_search import gauges
from tuning.league import COMPETITORS, VESSELS, LOWER, HIGHER, losses

F = {k: v for k, v in json.load(open(ROOT / "tuning/CLOSURE_FINAL_DEV.json")).items() if not k.startswith("_")}
CANDS = {src: {"closure": F[src]["closure"], "direct": F[src]["direct"], "speed": F[src]["speed"]} for src in F}
DEV, HELD = list(range(101, 131)), list(range(703001, 703031))


def omni(sc, v, cand):
    cl = dict(cand["closure"], site=(v == "multi"))
    return gauges(sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**cand["speed"]), omni_every=1,
                              direct_law=DirectLaw(**cand["direct"]), closure_law=ClosureLaw(**cl)))


def job(a):
    v, s, names = a
    sc = make_scenario(v, s)
    row = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    for nm in names:
        row["omni_" + nm] = omni(sc, v, CANDS[nm])
    return (v, s), row


def score(rows, seeds, nm):
    rng = np.random.default_rng(11)
    return [l for v in VESSELS for c in COMPETITORS for l in losses(rows, seeds, "omni_" + nm, c, v, rng)]


if __name__ == "__main__":
    with Pool(4) as p:
        rows = dict(p.map(job, [(v, s, list(CANDS)) for v in VESSELS for s in DEV], chunksize=1))
    dev = {nm: score(rows, DEV, nm) for nm in CANDS}
    for nm, L in dev.items():
        print("dev global =", nm, "setting:", len(L), "losing cells", flush=True)
    pick = min(CANDS, key=lambda nm: (len(dev[nm]), sum(l["omni_worse_by_pct"] for l in dev[nm])))
    pre = {"global_setting_from": pick, "setting": CANDS[pick], "heldout_seeds": HELD}
    pre["sha256"] = hashlib.sha256(json.dumps(pre, sort_keys=True).encode()).hexdigest()
    (ROOT / "tuning/GLOBAL_LEAGUE_PREREGISTRATION.json").write_text(json.dumps(pre, indent=1))
    with Pool(4) as p:
        rows = dict(p.map(job, [(v, s, [pick]) for v in VESSELS for s in HELD], chunksize=1))
    L = score(rows, HELD, pick)
    means = {v: {a: {m: float(np.mean([rows[(v, s)][a][m] for s in HELD])) for m in LOWER + HIGHER}
                 for a in COMPETITORS + ["omni_" + pick]} for v in VESSELS}
    print("heldout global", pick, len(L), "losing cells of 364")
    for v in VESSELS:
        print("  ", v, [(l["competitor"], l["gauge"], round(l["omni_worse_by_pct"], 1)) for l in L if l["vessel"] == v])
    (ROOT / "tuning/GLOBAL_LEAGUE.json").write_text(json.dumps({"preregistration": pre, "dev_losing_cells": {k: len(v) for k, v in dev.items()},
                                                               "heldout_cells": L, "means": means}, indent=1))
