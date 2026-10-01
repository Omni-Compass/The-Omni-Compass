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

GRID2 = [dict(lag=l, rise=0.0, lead=d, early=e, veto=False, flip_guard=f, confirm=k) for l, d, e, f, k in
         itertools.product([2, 4, 8], [1, 2, 3], [True, False], [0, 4, 8, 20, 40], [1, 3, 6]) if e or f]
GRID = [dict(lag=l, rise=r, lead=d, early=e, veto=vt) for l, r, d, e, vt in
        itertools.product([4, 8, 16], [0.0, 0.02, 0.05], [3, 6, 12], [True, False], [True, False]) if vt or r == 0.0]


def _job(args):
    v, s, grid = args
    sc = make_scenario(v, s)
    A = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    Bv = {(c, i): gauges(sim_slo.run(sc, "omniB:" + c, b_law=BLaw(**g))) for c in COMPETITORS for i, g in enumerate(grid)}
    return (v, s), A, Bv


def cells(A, Bv, seeds, v, c, i, rng):
    """Every gauge: A mean, B mean, change (positive = B better), paired bootstrap 95% CI of B - A, verdict."""
    out = {}
    for m in LOWER + HIGHER:
        a = np.array([A[(v, s)][c][m] for s in seeds], float); b = np.array([Bv[(v, s)][(c, i)][m] for s in seeds], float)
        d = b - a
        bs = d[rng.integers(0, len(d), (3000, len(d)))].mean(1); lo, hi = np.percentile(bs, [2.5, 97.5])
        better = (hi < 0) if m in LOWER else (lo > 0)
        worse = (lo > 0) if m in LOWER else (hi < 0)
        pct = (((a.mean() - b.mean()) if m in LOWER else (b.mean() - a.mean())) / abs(a.mean()) * 100) if abs(a.mean()) > 1e-9 else 0.0
        out[m] = {"A": float(a.mean()), "B": float(b.mean()), "better_pct": float(pct), "ci95": [float(lo), float(hi)],
                  "verdict": "better" if better else "worse" if worse else ("identical" if np.allclose(a, b) else "not significant")}
    return out


def gains(A, Bv, seeds, v, c, i):
    out = {}
    for m in LOWER + HIGHER:
        a = np.mean([A[(v, s)][c][m] for s in seeds]); b = np.mean([Bv[(v, s)][(c, i)][m] for s in seeds])
        if abs(a) > 1e-9:
            out[m] = ((a - b) if m in LOWER else (b - a)) / abs(a) * 100
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    fixed = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[2].endswith(".json") else None
    only = [a for a in sys.argv[2:] if a in VESSELS]
    if "--grid2" in sys.argv:
        GRID[:] = GRID2
    if "--strict" in sys.argv:
        import tuning.league as LG
        LG.TOL = 0.0025
    seeds = SEEDS[which]
    if "--seeds2" in sys.argv:
        seeds = list(range(700201, 700231))
    VESS = only or VESSELS
    with Pool(4) as p:
        res = p.map(_job, [(v, s, [fixed[v]] if fixed else GRID) for v in VESS for s in seeds], chunksize=1)
    A = {k: a for k, a, _ in res}; Bv = {k: b for k, _, b in res}
    rng = np.random.default_rng(11)
    out = {}
    for v in VESS:
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
                  "gains_pct": {c: gains(A, Bv, seeds, v, c, i) for c in COMPETITORS},
                  "cells": {c: cells(A, Bv, seeds, v, c, i, np.random.default_rng(5)) for c in COMPETITORS}, "seeds": seeds}
        print(f"{v}: B vs A losing cells {len(L)} with {grid[i]}")
        for l in L:
            print(f"    on {l['competitor']:13} {l['gauge']:16} B worse than A by {l['omni_worse_by_pct']:.1f}%")
        for c in COMPETITORS:
            gg = out[v]["gains_pct"][c]
            print(f"    on {c:13} " + ", ".join(f"{m} {x:+.1f}%" for m, x in gg.items() if abs(x) >= 1.0))
    tag = "_".join([which.upper()] + [a.strip("-").upper() for a in sys.argv[2:] if a.startswith("--")] + [v.upper() for v in only])
    (ROOT / f"tuning/B_LEAGUE_{tag}.json").write_text(json.dumps(out, indent=1))
