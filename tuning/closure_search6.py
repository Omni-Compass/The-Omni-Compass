"""Sixth closure pass (muscle tone: released machines are parked alive at low power with instant wake, a warm
reserve sized by the law; only machines beyond it are powered off). Built on the fifth pass: the two remaining negatives, attacked with the manuscript's math and queueing theory, around the
frozen energy-first settings (tuning/CLOSURE_FINAL_DEV.json):
  flipping   the deviation-bath band z (Chapter 31): a release must survive z standard deviations of the tracker's
             innovation over the release horizon; plus release hysteresis delta_rel and calm dwell
  response   square-root staffing (Halfin-Whitt) beta: replicas = busy + beta sqrt(busy) (web, multi)
Selection (development seeds, every variant kept): fewest energy/machine-hour losing cells, then fewest losing cells,
then smallest total gap. Usage: python tuning/closure_search6.py  ->  tuning/CLOSURE_SEARCH6_DEV.json"""
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

F = json.load(open(ROOT / "tuning/CLOSURE_FINAL_DEV.json"))
EN = ("energy_kwh", "node_hours")


def variants(v):
    betas = [-1.0, 1.0, 2.0] if v in ("web", "multi") else [-1.0]
    rm0 = F[v]["closure"]["rho_max"]
    return [dict(tone_H=th, rho_max=rm, delta=dl, z=z, beta=b)
            for th, rm, dl, z, b in itertools.product([240, 480, 960], sorted({rm0, 0.99}), [0.05, 0.02], [0.0, 1.0], betas)]


def cfg(v, x):
    f = F[v]
    return (dict(f["closure"], tone=True, tone_H=x["tone_H"], rho_max=x["rho_max"], delta=x["delta"], z=x["z"]),
            dict(f["direct"], beta=x["beta"]), f["speed"])


def _eval(args):
    v, x = args
    cl, dl, sl = cfg(v, x)
    return v, x, {s: gauges(sim_slo.run(make_scenario(v, s), "omni_closure", speed_law=SpeedLaw(**sl), omni_every=1,
                                        direct_law=DirectLaw(**dl), closure_law=ClosureLaw(**cl))) for s in SEEDS["dev"]}


if __name__ == "__main__":
    vessels = sys.argv[1:] or list(VESSELS)
    with Pool(4) as p:
        comp = {v: dict(p.map(_comp, [(v, s) for s in SEEDS["dev"]])) for v in vessels}
        res = p.map(_eval, [(v, x) for v in vessels for x in variants(v)], chunksize=2)
    out, allv = {}, {}
    for v in vessels:
        sc = [(score(v, comp[v], o), x) for vv, x, o in res if vv == v]
        allv[v] = [{"var": x, "losing_cells": n, "losses": L} for (n, m, L), x in sc]
        (n, m, L), x = min(sc, key=lambda q: (sum(l["gauge"] in EN for l in q[0][2]), q[0][0], q[0][1]))
        cl, dl, sl = cfg(v, x)
        out[v] = {"losing_cells": n, "closure": cl, "direct": dl, "speed": sl, "losses": L, "var": x}
        print(v, n, "losing cells", x, flush=True)
        for l in L:
            print(f"    {l['competitor']:13} {l['gauge']:16} omni worse by {l['omni_worse_by_pct']:.1f}%")
    (ROOT / "tuning/CLOSURE_SEARCH6_DEV.json").write_text(json.dumps({"picks": out, "all": allv}, indent=1))
