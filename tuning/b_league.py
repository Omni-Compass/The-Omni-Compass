"""Architecture B vs A: Omni-Compass on top of each platform against the same platform alone, every gauge, every vessel
(development seeds). Rule: no gauge worse (tuning/league.py loss rule). One BLaw setting per vessel, the same on every
platform. Usage: python tuning/b_league.py [dev|heldout] [settings.json]"""
import itertools, json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import BLaw
from tuning.speed_search import gauges, LOWER, HIGHER
from tuning.league import COMPETITORS, VESSELS, SEEDS, losses

GRID = [dict(lag=l, rise=r, lead=d, early=e, veto=vt) for l, r, d, e, vt in
        itertools.product([4, 8, 16], [0.0, 0.02, 0.05], [3, 6, 12], [True, False], [True, False]) if vt or r == 0.0]


def _job(args):
    v, s, grid = args
    sc = make_scenario(v, s)
    A = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    Bv = {(c, i): gauges(sim_slo.run(sc, "omniB:" + c, b_law=BLaw(**g))) for c in COMPETITORS for i, g in enumerate(grid)}
    return (v, s), A, Bv


def gains(A, Bv, seeds, v, c, i):
    out = {}
    for m in LOWER + HIGHER:
        a = np.mean([A[(v, s)][c][m] for s in seeds]); b = np.mean([Bv[(v, s)][(c, i)][m] for s in seeds])
        if abs(a) > 1e-9:
            out[m] = ((a - b) if m in LOWER else (b - a)) / abs(a) * 100
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    fixed = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
    seeds = SEEDS[which]
    with Pool(4) as p:
        res = p.map(_job, [(v, s, [fixed[v]] if fixed else GRID) for v in VESSELS for s in seeds], chunksize=1)
    A = {k: a for k, a, _ in res}; Bv = {k: b for k, _, b in res}
    rng = np.random.default_rng(11)
    out = {}
    for v in VESSELS:
        grid = [fixed[v]] if fixed else GRID
        best = None
        for i in range(len(grid)):
            L = []
            for c in COMPETITORS:
                rows = {(v, s): {"A": A[(v, s)][c], "B": Bv[(v, s)][(c, i)]} for s in seeds}
                L += [dict(l, competitor=c) for l in losses(rows, seeds, "B", "A", v, rng)]
            key = (len(L), -sum(max(0, g) for c in COMPETITORS for g in gains(A, Bv, seeds, v, c, i).values()))
            if best is None or key < best[0]:
                best = (key, i, L)
        _, i, L = best
        out[v] = {"setting": grid[i], "losing_cells": len(L), "losses": L,
                  "gains_pct": {c: gains(A, Bv, seeds, v, c, i) for c in COMPETITORS}}
        print(f"{v}: B vs A losing cells {len(L)} with {grid[i]}")
        for l in L:
            print(f"    on {l['competitor']:13} {l['gauge']:16} B worse than A by {l['omni_worse_by_pct']:.1f}%")
        for c in COMPETITORS:
            gg = out[v]["gains_pct"][c]
            print(f"    on {c:13} " + ", ".join(f"{m} {x:+.1f}%" for m, x in gg.items() if abs(x) >= 1.0))
    (ROOT / f"tuning/B_LEAGUE_{which.upper()}.json").write_text(json.dumps(out, indent=1))
