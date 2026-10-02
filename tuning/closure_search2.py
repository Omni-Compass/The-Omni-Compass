# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Second closure-law pass: release hysteresis (delta_rel) and calm-set dwell (resource-aware envelope, Proposition 2),
around each vessel's first-pass winner (tuning/CLOSURE_SEARCH_DEV.json). Development seeds only; scored by losing cells
against the seven platforms. Usage: python tuning/closure_search2.py  ->  tuning/CLOSURE_SEARCH2_DEV.json"""
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
FIRST = json.load(open(ROOT / "tuning/CLOSURE_SEARCH_DEV.json"))
VAR = [dict(delta_rel=dr, dwell=dw, H_rel=hr, b=b)
       for dr, dw, hr, b in itertools.product([-1.0, 0.15, 0.3], [0, 20, 40, 80, 160], [40, 160], [0.02, 0.005])]


def law(v, i):
    return {**FIRST[v]["closure"], **VAR[i]}


def _eval(args):
    v, i = args
    return v, i, {s: gauges(sim_slo.run(make_scenario(v, s), "omni_closure", speed_law=SpeedLaw(**SL), omni_every=1,
                                        direct_law=DirectLaw(**FIRST[v]["direct"]), closure_law=ClosureLaw(**law(v, i))))
                  for s in SEEDS["dev"]}


if __name__ == "__main__":
    vessels = sys.argv[1:] or list(VESSELS)
    with Pool(4) as p:
        comp = {v: dict(p.map(_comp, [(v, s) for s in SEEDS["dev"]])) for v in vessels}
        res = p.map(_eval, [(v, i) for v in vessels for i in range(len(VAR))], chunksize=2)
    out = {}
    for v in vessels:
        ranked = sorted(((*score(v, comp[v], o)[:2], i, score(v, comp[v], o)[2]) for vv, i, o in res if vv == v))
        n, mag, i, L = ranked[0]
        out[v] = {"losing_cells": n, "closure": law(v, i), "direct": FIRST[v]["direct"], "losses": L}
        print(v, n, "losing cells", law(v, i))
        for l in L:
            print(f"    {l['competitor']:13} {l['gauge']:16} omni worse by {l['omni_worse_by_pct']:.1f}%")
    (ROOT / "tuning/CLOSURE_SEARCH2_DEV.json").write_text(json.dumps(out, indent=1))
