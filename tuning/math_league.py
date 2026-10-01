"""League count for the math-driven governor (omnicompass/mathdrive.py): grid of MathLaw settings per vessel against
the seven platforms, development seeds, same loss rule as tuning/league.py. Usage: python tuning/math_league.py"""
import itertools, json, sys
from multiprocessing import Pool
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from omnicompass.mathdrive import MathLaw
from tuning.speed_search import gauges
from tuning.league import SEEDS, VESSELS
from tuning.attack import _comp, score

GRID = [dict(clock=c, g_w=g, w_release=r, dwell=d, g_cap=gc)
        for c, g, r, d, gc in itertools.product([0.1, 0.3, 1.0, 3.0], [0.5, 1.0, 2.0], [0.01, 0.05], [3, 10], [0.0, 0.5])]


def _eval(args):
    v, i = args
    law = MathLaw(**GRID[i])
    return v, i, {s: gauges(sim_slo.run(make_scenario(v, s), "omni_math", omni_every=4, math_law=law)) for s in SEEDS["dev"]}


if __name__ == "__main__":
    with Pool(4) as p:
        comp = {v: dict(p.map(_comp, [(v, s) for s in SEEDS["dev"]])) for v in VESSELS}
        res = p.map(_eval, [(v, i) for v in VESSELS for i in range(len(GRID))], chunksize=2)
    best = {}
    for v, i, o in res:
        n, mag, L = score(v, comp[v], o)
        if v not in best or (n, mag) < best[v][:2]:
            best[v] = (n, mag, i, L)
    out = {v: {"losing_cells": b[0], "setting": GRID[b[2]], "losses": b[3]} for v, b in best.items()}
    (ROOT / "tuning/MATH_LEAGUE_DEV.json").write_text(json.dumps(out, indent=1))
    tot = 0
    for v, b in out.items():
        tot += b["losing_cells"]
        print(v, b["losing_cells"], "losing cells, setting", b["setting"])
        for l in b["losses"]:
            print(f"    {l['competitor']:13} {l['gauge']:16} omni worse by {l['omni_worse_by_pct']:.1f}%")
    print("TOTAL", tot)
