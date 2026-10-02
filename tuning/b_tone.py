# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Architecture B, second generation: muscle tone and consolidation on top of each platform. For every (workload,
platform) the candidates are the frozen B setting (tuning/B_SETTINGS_PER_PLATFORM.json) and that setting plus
  tone     the platform's power-offs become parks (instant wake), reserve horizon tone_H at packing tone_rho
  pack     Omni consolidates on top: remove a machine when the rest hold every request at this packing, after calm
Selection on development seeds: no losing cell under the strict tolerance (0.25%), then the largest total gain (losses
penalised x3), so the result can only be equal to or better than the frozen B. Held-out on fresh seeds 700401-700430.
Usage: python tuning/b_tone.py dev   ->  tuning/B_SETTINGS_TONE.json
       python tuning/b_tone.py heldout  ->  tuning/B_TONE_HELDOUT.json (frozen by SHA-256 in B_TONE_PREREGISTRATION.json)"""
import hashlib, itertools, json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import tuning.league as LG
from tuning.league import COMPETITORS, SEEDS, VESSELS, losses
from tuning.b_league import gains, cells
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import BLaw
from tuning.speed_search import gauges

BASE = json.load(open(ROOT / "tuning/B_SETTINGS_PER_PLATFORM.json"))
ADD = [{}] + [dict(tone=True, tone_H=h, tone_rho=r, pack=pk) for h, r, pk in
              itertools.product([24, 96, 240, 960], [0.95, 0.99], [0.0, 0.8, 0.9, 0.95])]
HELD = list(range(700401, 700431))


def _job(a):
    v, s = a
    sc = make_scenario(v, s)
    A = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    Bv = {(c, i): gauges(sim_slo.run(sc, "omniB:" + c, b_law=BLaw(**dict(BASE[v][c], **x)))) for c in COMPETITORS
          for i, x in enumerate(ADD)}
    return (v, s), A, Bv


def _ho(a):
    v, s, per = a
    sc = make_scenario(v, s)
    return (v, s), {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}, \
        {(c, 0): gauges(sim_slo.run(sc, "omniB:" + c, b_law=BLaw(**per[c]))) for c in COMPETITORS}


if __name__ == "__main__" and sys.argv[1] == "dev":
    LG.TOL = 0.0025
    seeds = SEEDS["dev"]
    with Pool(4) as p:
        res = p.map(_job, [(v, s) for v in VESSELS for s in seeds], chunksize=1)
    A = {k: a for k, a, _ in res}; Bv = {k: b for k, _, b in res}
    out = {}
    for v in VESSELS:
        out[v] = {}
        for c in COMPETITORS:
            best = None
            for i in range(len(ADD)):
                rows = {(v, s): {"A": A[(v, s)][c], "B": Bv[(v, s)][(c, i)]} for s in seeds}
                L = losses(rows, seeds, "B", "A", v, np.random.default_rng(11))
                g = gains(A, Bv, seeds, v, c, i)
                key = (len(L), -(sum(max(0.0, x) for x in g.values()) - 3.0 * sum(max(0.0, -x) for x in g.values())))
                if best is None or key < best[0]:
                    best = (key, i, g)
            out[v][c] = dict(BASE[v][c], **ADD[best[1]])
            print(v, c, "losses", best[0][0], ADD[best[1]] or "frozen B", {m: round(x, 1) for m, x in best[2].items() if abs(x) >= 1}, flush=True)
    (ROOT / "tuning/B_SETTINGS_TONE.json").write_text(json.dumps(out, indent=1))
elif __name__ == "__main__":
    LG.TOL = 0.005
    per = json.load(open(ROOT / "tuning/B_SETTINGS_TONE.json"))
    blob = json.dumps(per, sort_keys=True)
    (ROOT / "tuning/B_TONE_PREREGISTRATION.json").write_text(json.dumps(
        {"settings_sha256": hashlib.sha256(blob.encode()).hexdigest(), "heldout_seeds": HELD,
         "sim_slo_sha256": hashlib.sha256((ROOT / "fleet/sim_slo.py").read_bytes()).hexdigest()}, indent=1))
    with Pool(4) as p:
        res = p.map(_ho, [(v, s, per[v]) for v in VESSELS for s in HELD], chunksize=1)
    A = {k: a for k, a, _ in res}; Bv = {k: b for k, _, b in res}
    out = {}
    for v in VESSELS:
        Ls, cellm, gm = [], {}, {}
        for c in COMPETITORS:
            rows = {(v, s): {"A": A[(v, s)][c], "B": Bv[(v, s)][(c, 0)]} for s in HELD}
            Ls += [dict(l, competitor=c) for l in losses(rows, HELD, "B", "A", v, np.random.default_rng(11))]
            cellm[c] = cells(A, Bv, HELD, v, c, 0, np.random.default_rng(5))
            gm[c] = gains(A, Bv, HELD, v, c, 0)
        out[v] = {"setting": per[v], "losing_cells": len(Ls), "losses": Ls, "gains_pct": gm, "cells": cellm, "seeds": HELD}
        print(v, "losing cells", len(Ls), [(l["competitor"], l["gauge"], round(l["omni_worse_by_pct"], 2)) for l in Ls], flush=True)
    (ROOT / "tuning/B_TONE_HELDOUT.json").write_text(json.dumps(out, indent=1))
    print("TOTAL losing cells", sum(r["losing_cells"] for r in out.values()), "of", 13 * 7 * 4)
