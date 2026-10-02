# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Closure governor (omnicompass/closure.py) in strict C: grid over the closure-law constants per vessel, development seeds,
scored by losing cells against the seven platforms (tuning/league.py rule). Usage: python tuning/closure_search.py"""
import itertools, json, sys
from multiprocessing import Pool
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import DirectLaw
from omnicompass.speed import SpeedLaw
from omnicompass.closure import ClosureLaw
from tuning.speed_search import gauges
from tuning.league import SEEDS, VESSELS
from tuning.attack import _comp, score

SL = dict(rho0=0.7, rho_min=0.7, kI=0.0, kE=0.0)
GRID = [dict(rho_max=rm, delta=dl, H_add=ha, H_rel=hr, a=a, b=b, g=0.05, push_release=0.2, turn=True)
        for rm, dl, ha, hr, a, b in itertools.product([0.9, 0.97], [0.05, 0.15], [6, 12], [40, 160], [0.2, 0.5], [0.02, 0.1])]
DGRID = [dict(window=20, kb=1.0, push_release=0.2, tol=0.0), dict(window=40, kb=0.5, push_release=0.2, tol=0.1)]


def _eval(args):
    v, i, j = args
    return v, i, j, {s: gauges(sim_slo.run(make_scenario(v, s), "omni_closure", speed_law=SpeedLaw(**SL), omni_every=1,
                                           direct_law=DirectLaw(**DGRID[j]), closure_law=ClosureLaw(**GRID[i]))) for s in SEEDS["dev"]}


if __name__ == "__main__":
    vessels = sys.argv[1:] or list(VESSELS)
    with Pool(4) as p:
        comp = {v: dict(p.map(_comp, [(v, s) for s in SEEDS["dev"]])) for v in vessels}
        res = p.map(_eval, [(v, i, j) for v in vessels for i in range(len(GRID)) for j in range(len(DGRID))], chunksize=2)
    out = {}
    for v in vessels:
        best = None
        for vv, i, j, o in res:
            if vv != v:
                continue
            n, mag, L = score(v, comp[v], o)
            if best is None or (n, mag) < best[:2]:
                best = (n, mag, i, j, L)
        out[v] = {"losing_cells": best[0], "closure": GRID[best[2]], "direct": DGRID[best[3]], "losses": best[4]}
        print(v, best[0], "losing cells", GRID[best[2]], DGRID[best[3]])
        for l in best[4]:
            print(f"    {l['competitor']:13} {l['gauge']:16} omni worse by {l['omni_worse_by_pct']:.1f}%")
    (ROOT / "tuning/CLOSURE_SEARCH_DEV.json").write_text(json.dumps(out, indent=1))
