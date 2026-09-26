"""Whole body at multi-cluster sites (four clusters, one site). B: each platform's frozen setting with and without traffic
shift; C: the closure law on the site total (one forecast, one warm reserve) with traffic shift, against each incumbent.
Selection on 30 development seeds (101-130): no losing cell (strict 0.25% for B, league rule for C), then largest gain;
frozen by SHA-256, then fresh held-out seeds 701001-701030. Traffic shift assumes each service can run in every cluster of
the site (replicated services) and adds SHIFT_MS to requests served in another cluster.
Usage: python tuning/site_league.py  ->  tuning/SITE_LEAGUE.json"""
import hashlib, itertools, json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import tuning.league as LG
from tuning.league import COMPETITORS, losses
from tuning.b_league import gains
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import BLaw, DirectLaw
from omnicompass.speed import SpeedLaw
from omnicompass.closure import ClosureLaw
from tuning.speed_search import gauges

V = "multi"
DEV, HELD = list(range(101, 131)), list(range(701001, 701031))
TONE = json.load(open(ROOT / "tuning/B_SETTINGS_TONE.json"))[V]
FIX = json.load(open(ROOT / "tuning/B_FIX.json"))["preregistration"]["chosen"]
F = json.load(open(ROOT / "tuning/CLOSURE_FINAL_DEV.json"))[V]


def bcands(c):
    base = dict(FIX.get(f"{V}|{c}", TONE[c]))
    return [base, dict(base, shift=True)]


CV = [dict(tone_H=th, rho=r, rho_max=rm, turn=tu) for th, r, rm, tu in
      itertools.product([0, 24, 96, 960], [0.7, 0.72], [0.97, 1.0], [True, False])]


def claw(x):
    cl = dict(F["closure"], site=True, tone=x["tone_H"] > 0, tone_H=max(1, x["tone_H"]), rho_max=x["rho_max"], turn=x["turn"],
              delta=0.0 if x["rho_max"] >= 1.0 else 0.02, delta_rel=0.0 if x["rho_max"] >= 1.0 else 0.08, H_rel=10, H_add=2)
    return cl, dict(F["speed"], rho0=x["rho"], rho_min=x["rho"])


def omni(sc, x):
    cl, sl = claw(x)
    return gauges(sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**sl), omni_every=1, direct_law=DirectLaw(**F["direct"]),
                              closure_law=ClosureLaw(**cl)))


def _job(a):
    s, pickB, pickC = a
    sc = make_scenario(V, s)
    A = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    if pickB is None:
        Bv = {c: [gauges(sim_slo.run(sc, "omniB:" + c, b_law=BLaw(**x))) for x in bcands(c)] for c in COMPETITORS}
        Cv = [omni(sc, x) for x in CV]
    else:
        Bv = {c: [gauges(sim_slo.run(sc, "omniB:" + c, b_law=BLaw(**pickB[c])))] for c in COMPETITORS}
        Cv = {c: omni(sc, pickC[c]) for c in COMPETITORS}
    return s, A, Bv, Cv


def judge(res, seeds, c, getB, strict):
    LG.TOL = 0.0025 if strict else 0.005
    rows = {(V, s): {"A": res[s][0][c], "B": getB(s)} for s in seeds}
    L = losses(rows, seeds, "B", "A", V, np.random.default_rng(11))
    Aa = {(V, s): {c: res[s][0][c]} for s in seeds}; Bb = {(V, s): {(c, 0): getB(s)} for s in seeds}
    return L, gains(Aa, Bb, seeds, V, c, 0)


def key(L, g):
    return (len(L), -(sum(max(0.0, x) for x in g.values()) - 3 * sum(max(0.0, -x) for x in g.values())))


if __name__ == "__main__":
    with Pool(4) as p:
        r = p.map(_job, [(s, None, None) for s in DEV], chunksize=1)
    res = {s: (A, Bv, Cv) for s, A, Bv, Cv in r}
    pickB, pickC = {}, {}
    for c in COMPETITORS:
        bb = min(range(2), key=lambda i: key(*judge(res, DEV, c, lambda s: res[s][1][c][i], True)))
        pickB[c] = bcands(c)[bb]
        cc = min(range(len(CV)), key=lambda i: key(*judge(res, DEV, c, lambda s: res[s][2][i], False)))
        pickC[c] = CV[cc]
        print("dev", c, "B", "shift" if pickB[c].get("shift") else "no shift", "C", CV[cc], flush=True)
    pre = {"B": pickB, "C": pickC, "heldout_seeds": HELD}
    pre["sha256"] = hashlib.sha256(json.dumps(pre, sort_keys=True).encode()).hexdigest()
    (ROOT / "tuning/SITE_LEAGUE_PREREGISTRATION.json").write_text(json.dumps(pre, indent=1))
    with Pool(4) as p:
        r = p.map(_job, [(s, pickB, pickC) for s in HELD], chunksize=1)
    res = {s: (A, Bv, Cv) for s, A, Bv, Cv in r}
    out = {"preregistration": pre, "B": {}, "C": {}}
    for c in COMPETITORS:
        L, g = judge(res, HELD, c, lambda s: res[s][1][c][0], False)
        out["B"][c] = {"losses": L, "gains_pct": g}
        L2, g2 = judge(res, HELD, c, lambda s: res[s][2][c], False)
        out["C"][c] = {"losses": L2, "gains_pct": g2}
        print("heldout", c, "B losses", [(l["gauge"], round(l["omni_worse_by_pct"], 1)) for l in L],
              "| C losses", [(l["gauge"], round(l["omni_worse_by_pct"], 1)) for l in L2], flush=True)
    (ROOT / "tuning/SITE_LEAGUE.json").write_text(json.dumps(out, indent=1))
