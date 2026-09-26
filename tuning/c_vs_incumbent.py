"""Architecture C against each incumbent separately. A buyer replaces one platform, so for every (workload, incumbent)
the closure law's levers are searched for an operating point with no losing cell against that incumbent (13 gauges,
league loss rule): warm-reserve horizon tone_H, pod target rho*, exact M/M/c staffing wq, packing boundary rho_max,
release band delta_rel. Development seeds choose; the chosen points are frozen by SHA-256 and run once on fresh held-out
seeds 700501-700530. Second round (--wide): selection on 30 development seeds (101-130) to stop over-fitting to 10, batch
also tries a safer packing boundary; held-out on fresh seeds 700601-700630.
Usage: python tuning/c_vs_incumbent.py dev | heldout [--wide]"""
import hashlib, itertools, json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import DirectLaw
from omnicompass.speed import SpeedLaw
from omnicompass.closure import ClosureLaw
from tuning.speed_search import gauges
from tuning.league import COMPETITORS, SEEDS, VESSELS, losses

VES = ["web", "multi"] if "--round3" in sys.argv else VESSELS
F = {k: v for k, v in json.load(open(ROOT / "tuning/CLOSURE_FINAL_DEV.json")).items() if not k.startswith("_")}
R3 = "--round3" in sys.argv          # web and multi only: pods near the platforms' fill, packing to the boundary, short release look-ahead
WIDE = "--wide" in sys.argv or R3
HELD = list(range(700801, 700831)) if R3 else list(range(700601, 700631)) if WIDE else list(range(700501, 700531))
TAG = "_R3" if R3 else "_WIDE" if WIDE else ""


def variants(v):
    if v in ("web", "multi") and R3:
        return [dict(tone_H=th, rho=r, wq=-1.0, rho_max=rm, turn=tu, H_rel=hr, delta=0.0 if rm >= 1.0 else 0.02,
                     delta_rel=0.0 if rm >= 1.0 else 0.08, H_add=2)
                for th, r, rm, tu, hr in itertools.product([0, 24, 960], [0.7, 0.72, 0.75, 0.8], [0.97, 1.0], [True, False], [10, 40])]
    if v in ("web", "multi"):
        return [dict(tone_H=th, rho=r, wq=wq, rho_max=rm) for th, r, wq, rm in
                itertools.product([24, 96, 960], [0.7, 0.75, 0.8], [-1.0, 0.05, 0.1], [0.97, 0.99])]
    return [dict(tone_H=th, rho_max=rm, delta_rel=dr, H_add=ha) for th, rm, dr, ha in
            itertools.product([0, 24, 96, 960], [0.93, 0.95, 0.97, 0.99] if WIDE else [0.97, 0.99], [0.08, 0.15], [6, 12])]


def law(v, x):
    f = F[v]; cl = dict(f["closure"]); dl = dict(f["direct"]); sl = dict(f["speed"])
    if "tone_H" in x:
        cl.update(tone=x["tone_H"] > 0, tone_H=max(1, x["tone_H"]))
    for k in ("rho_max", "delta_rel", "H_add", "delta", "turn", "H_rel"):
        if k in x:
            cl[k] = x[k]
    if "rho" in x:
        sl.update(rho0=x["rho"], rho_min=x["rho"])
    if "wq" in x:
        dl["wq"] = x["wq"]
    return cl, dl, sl


def run_omni(sc, v, x):
    cl, dl, sl = law(v, x)
    return gauges(sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**sl), omni_every=1, direct_law=DirectLaw(**dl),
                              closure_law=ClosureLaw(**cl)))


def _dev(a):
    v, s = a
    sc = make_scenario(v, s)
    return (v, s), {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}, [run_omni(sc, v, x) for x in variants(v)]


def _ho(a):
    v, s, pick = a
    sc = make_scenario(v, s)
    return (v, s), {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}, {c: run_omni(sc, v, pick[c]) for c in COMPETITORS}


if __name__ == "__main__" and sys.argv[1] == "dev":
    seeds = list(range(101, 131)) if WIDE else SEEDS["dev"]
    with Pool(4) as p:
        res = p.map(_dev, [(v, s) for v in VES for s in seeds], chunksize=1)
    A = {k: a for k, a, _ in res}; O = {k: o for k, _, o in res}
    out = {}
    for v in VES:
        out[v] = {}
        for c in COMPETITORS:
            best = None
            for i, x in enumerate(variants(v)):
                rows = {(v, s): {"inc": A[(v, s)][c], "omni": O[(v, s)][i]} for s in seeds}
                L = losses(rows, seeds, "omni", "inc", v, np.random.default_rng(11))
                key = (len(L), sum(l["omni_worse_by_pct"] for l in L))
                if best is None or key < best[0]:
                    best = (key, x, L)
            out[v][c] = {"var": best[1], "losing_cells": best[0][0], "losses": best[2]}
            print(v, c, "losing cells", best[0][0], best[1],
                  [(l["gauge"], round(l["omni_worse_by_pct"], 1)) for l in best[2]], flush=True)
    (ROOT / f"tuning/C_VS_INCUMBENT{TAG}_DEV.json").write_text(json.dumps(out, indent=1))
elif __name__ == "__main__":
    dev = json.load(open(ROOT / f"tuning/C_VS_INCUMBENT{TAG}_DEV.json"))
    pick = {v: {c: dev[v][c]["var"] for c in COMPETITORS} for v in VES}
    (ROOT / f"tuning/C_VS_INCUMBENT{TAG}_PREREGISTRATION.json").write_text(json.dumps(
        {"picks": pick, "sha256": hashlib.sha256(json.dumps(pick, sort_keys=True).encode()).hexdigest(),
         "base_settings": "tuning/CLOSURE_FINAL_DEV.json", "heldout_seeds": HELD}, indent=1))
    with Pool(4) as p:
        res = p.map(_ho, [(v, s, pick[v]) for v in VES for s in HELD], chunksize=1)
    A = {k: a for k, a, _ in res}; O = {k: o for k, _, o in res}
    out = {"seeds": HELD, "picks": pick, "cells": {}, "means": {}}
    for v in VES:
        out["cells"][v] = {}; out["means"][v] = {}
        for c in COMPETITORS:
            rows = {(v, s): {"inc": A[(v, s)][c], "omni": O[(v, s)][c]} for s in HELD}
            L = losses(rows, HELD, "omni", "inc", v, np.random.default_rng(11))
            out["cells"][v][c] = L
            out["means"][v][c] = {g: {"incumbent": float(np.mean([A[(v, s)][c][g] for s in HELD])),
                                      "omni": float(np.mean([O[(v, s)][c][g] for s in HELD]))}
                                  for g in ("energy_kwh", "node_hours", "p95_ms", "p99_ms", "mean_ms", "start_stop", "work_completed")}
            print(v, c, "losing cells", len(L), [(l["gauge"], round(l["omni_worse_by_pct"], 1)) for l in L], flush=True)
    (ROOT / f"tuning/C_VS_INCUMBENT{TAG}_HELDOUT.json").write_text(json.dumps(out, indent=1))
    print("TOTAL", sum(len(x) for v in out["cells"].values() for x in v.values()), "of", 13 * 7 * 4)
