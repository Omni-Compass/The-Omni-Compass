"""Fourth closure pass (web, multi): spend the response-time margin on energy. Strict C already answers far faster than
every platform, so the pod utilisation target rho* (speed law rho0 = rho_min) is raised above the platforms' 70% and the
replica release window/backlog gain are varied, on top of the third pass's machine-law picks (both). Development seeds;
every variant kept. Usage: python tuning/closure_search4.py  ->  tuning/CLOSURE_SEARCH4_DEV.json"""
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

P3 = json.load(open(ROOT / "tuning/CLOSURE_SEARCH3_DEV.json"))["picks"]
EN = ("energy_kwh", "node_hours")
VAR = [dict(pick=pk, rho=r, window=w, kb=kb) for pk, r, w, kb in
       itertools.product(["energy_first", "count"], [0.7, 0.8, 0.85, 0.9], [10, 20, 40], [0.5, 1.0])]


def cfg(v, i):
    x = VAR[i]; p = P3[v][x["pick"]]
    return (p["closure"], dict(p["direct"], window=x["window"], kb=x["kb"]), dict(rho0=x["rho"], rho_min=x["rho"], kI=0.0, kE=0.0))


def _eval(args):
    v, i = args
    cl, dl, sl = cfg(v, i)
    return v, i, {s: gauges(sim_slo.run(make_scenario(v, s), "omni_closure", speed_law=SpeedLaw(**sl), omni_every=1,
                                        direct_law=DirectLaw(**dl), closure_law=ClosureLaw(**cl))) for s in SEEDS["dev"]}


if __name__ == "__main__":
    vessels = sys.argv[1:] or ["web", "multi"]
    with Pool(4) as p:
        comp = {v: dict(p.map(_comp, [(v, s) for s in SEEDS["dev"]])) for v in vessels}
        res = p.map(_eval, [(v, i) for v in vessels for i in range(len(VAR))], chunksize=2)
    out, allv = {}, {}
    for v in vessels:
        sc = [(score(v, comp[v], o), i) for vv, i, o in res if vv == v]
        allv[v] = [{"var": VAR[i], "losing_cells": n, "losses": L} for (n, m, L), i in sc]
        e_n = lambda L: sum(l["gauge"] in EN for l in L)
        e_m = lambda L: sum(l["omni_worse_by_pct"] for l in L if l["gauge"] in EN)
        for tag, key in (("count", lambda x: (x[0][0], x[0][1])), ("energy_first", lambda x: (e_n(x[0][2]), e_m(x[0][2]), x[0][0]))):
            (n, m, L), i = min(sc, key=key)
            cl, dl, sl = cfg(v, i)
            out.setdefault(v, {})[tag] = {"losing_cells": n, "closure": cl, "direct": dl, "speed": sl, "losses": L}
            print(v, tag, n, "losing cells", VAR[i])
            for l in L:
                print(f"    {l['competitor']:13} {l['gauge']:16} omni worse by {l['omni_worse_by_pct']:.1f}%")
    (ROOT / "tuning/CLOSURE_SEARCH4_DEV.json").write_text(json.dumps({"picks": out, "all": allv}, indent=1))
