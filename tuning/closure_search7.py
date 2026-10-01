"""Seventh closure pass: web is settled by pass 6; this pass attacks what pass 6 left on four clusters (typical response)
and batch (slowest jobs, energy against the packers). Built on the pass-6 picks; development seeds; every variant kept;
same energy-first selection. Usage: python tuning/closure_search7.py  ->  tuning/CLOSURE_SEARCH7_DEV.json"""
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
from tuning.league import SEEDS
from tuning.attack import _comp, score

P6 = json.load(open(ROOT / "tuning/CLOSURE_SEARCH6_DEV.json"))["picks"]
EN = ("energy_kwh", "node_hours")


def variants(v):
    if v == "multi":
        return [dict(speed=dict(rho0=r, rho_min=r, kI=0.0, kE=0.0), direct=dict(beta=b), closure=dict(tone_H=th, z=z))
                for r, b, th, z in itertools.product([0.7, 0.75, 0.8, 0.85], [-1.0, 1.0, 2.0], [480, 960], [0.0, 1.0])]
    return [dict(speed={}, direct={}, closure=dict(rho_max=rm, delta=dl, tone=tn, tone_H=th, delta_rel=dr, H_add=ha))
            for rm, dl, tn, th, dr, ha in itertools.product([0.97, 0.99], [0.02, 0.05], [True, False], [240, 960],
                                                            [0.08, 0.15], [6, 12]) if tn or th == 960]


def cfg(v, x):
    p = P6[v]
    return dict(p["closure"], **x["closure"]), dict(p["direct"], **x["direct"]), dict(p["speed"], **x["speed"])


def _eval(args):
    v, i = args
    cl, dl, sl = cfg(v, variants(v)[i])
    return v, i, {s: gauges(sim_slo.run(make_scenario(v, s), "omni_closure", speed_law=SpeedLaw(**sl), omni_every=1,
                                        direct_law=DirectLaw(**dl), closure_law=ClosureLaw(**cl))) for s in SEEDS["dev"]}


if __name__ == "__main__":
    vessels = sys.argv[1:] or ["multi", "batch"]
    with Pool(4) as p:
        comp = {v: dict(p.map(_comp, [(v, s) for s in SEEDS["dev"]])) for v in vessels}
        res = p.map(_eval, [(v, i) for v in vessels for i in range(len(variants(v)))], chunksize=2)
    out, allv = {}, {}
    for v in vessels:
        sc = [(score(v, comp[v], o), i) for vv, i, o in res if vv == v]
        allv[v] = [{"var": variants(v)[i], "losing_cells": n, "losses": L} for (n, m, L), i in sc]
        (n, m, L), i = min(sc, key=lambda q: (sum(l["gauge"] in EN for l in q[0][2]), q[0][0], q[0][1]))
        cl, dl, sl = cfg(v, variants(v)[i])
        out[v] = {"losing_cells": n, "closure": cl, "direct": dl, "speed": sl, "losses": L, "var": variants(v)[i]}
        print(v, n, "losing cells", variants(v)[i], flush=True)
        for l in L:
            print(f"    {l['competitor']:13} {l['gauge']:16} omni worse by {l['omni_worse_by_pct']:.1f}%")
    (ROOT / "tuning/CLOSURE_SEARCH7_DEV.json").write_text(json.dumps({"picks": out, "all": allv}, indent=1))
