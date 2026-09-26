"""Architecture B with one setting per (workload, platform): Omni-Compass knows which platform it governs. For each pair,
choose on development seeds the setting with no loss under the strict tolerance (0.25%) and the largest total gain.
Usage: python tuning/b_per_platform.py VESSEL [VESSEL...]"""
import json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import tuning.league as LG
from tuning.league import COMPETITORS, SEEDS, losses
from tuning.b_league import GRID, _job, gains

LG.TOL = 0.0025
if __name__ == "__main__" and sys.argv[1] == "--heldout":
    LG.TOL = 0.005
    settings = json.load(open(ROOT / "tuning/B_SETTINGS_PER_PLATFORM.json"))
    res = heldout(settings, list(range(700201, 700231)))
    (ROOT / "tuning/B_LEAGUE_HELDOUT2.json").write_text(json.dumps(res, indent=1))
    print("TOTAL losing cells", sum(r["losing_cells"] for r in res.values()), "of", 13 * 7 * 4)
elif __name__ == "__main__":
    vessels = sys.argv[1:]
    seeds = SEEDS["dev"]
    with Pool(4) as p:
        res = p.map(_job, [(v, s, GRID) for v in vessels for s in seeds], chunksize=1)
    A = {k: a for k, a, _ in res}; Bv = {k: b for k, _, b in res}
    path = ROOT / "tuning/B_SETTINGS_PER_PLATFORM.json"
    out = json.loads(path.read_text()) if path.exists() else {}
    for v in vessels:
        out[v] = {}
        for c in COMPETITORS:
            best = None
            for i in range(len(GRID)):
                rows = {(v, s): {"A": A[(v, s)][c], "B": Bv[(v, s)][(c, i)]} for s in seeds}
                L = losses(rows, seeds, "B", "A", v, np.random.default_rng(11))
                g = gains(A, Bv, seeds, v, c, i)
                key = (len(L), -(sum(max(0.0, x) for x in g.values()) - 3.0 * sum(max(0.0, -x) for x in g.values())))
                if best is None or key < best[0]:
                    best = (key, i, g)
            out[v][c] = GRID[best[1]]
            print(v, c, "losses", best[0][0], GRID[best[1]], {m: round(x, 1) for m, x in best[2].items() if abs(x) >= 1})
    path.write_text(json.dumps(out, indent=1))


def heldout(settings, seeds):
    """Run the frozen per-platform settings on held-out seeds; same output format as tuning/b_league.py."""
    from fleet import sim_slo
    from fleet.harness import make_scenario
    from fleet.sim_slo import BLaw
    from tuning.speed_search import gauges
    from tuning.b_league import cells
    out = {}
    for v in LG.VESSELS:
        with Pool(4) as p:
            res = p.map(_ho_job, [(v, s, settings[v]) for s in seeds], chunksize=1)
        A = {k: a for k, a, _ in res}; Bv = {k: b for k, _, b in res}
        Ls, cellm, gm = [], {}, {}
        for c in COMPETITORS:
            rows = {(v, s): {"A": A[(v, s)][c], "B": Bv[(v, s)][(c, 0)]} for s in seeds}
            Ls += [dict(l, competitor=c) for l in losses(rows, seeds, "B", "A", v, np.random.default_rng(11))]
            cellm[c] = cells(A, Bv, seeds, v, c, 0, np.random.default_rng(5))
            gm[c] = gains(A, Bv, seeds, v, c, 0)
        out[v] = {"setting": settings[v], "losing_cells": len(Ls), "losses": Ls, "gains_pct": gm, "cells": cellm, "seeds": seeds}
        print(v, "losing cells", len(Ls), [(l["competitor"], l["gauge"], round(l["omni_worse_by_pct"], 2)) for l in Ls], flush=True)
    return out


def _ho_job(args):
    from fleet import sim_slo
    from fleet.harness import make_scenario
    from fleet.sim_slo import BLaw
    from tuning.speed_search import gauges
    v, s, per = args
    sc = make_scenario(v, s)
    A = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    Bv = {(c, 0): gauges(sim_slo.run(sc, "omniB:" + c, b_law=BLaw(**per[c]))) for c in COMPETITORS}
    return (v, s), A, Bv
