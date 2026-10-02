# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Architecture B, the pairs left after tuning/B_TONE_HELDOUT.json: four clusters on AKS NAP (pod changes), batch on
Turbonomic (energy, machine-hours) and four clusters on CAST AI (equal, no gain). Wider candidate set, selection on 30
development seeds (101-130) under the strict tolerance: no losing cell AND at least one gauge better by >= 1%; the frozen
B_SETTINGS_TONE setting stays a candidate. Held-out on fresh seeds 700701-700730.
Usage: python tuning/b_fix.py  ->  tuning/B_FIX.json"""
import hashlib, itertools, json, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import tuning.league as LG
from tuning.league import losses
from tuning.b_league import gains
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import BLaw
from tuning.speed_search import gauges

PAIRS = [("multi", "aks_nap"), ("batch", "turbonomic"), ("multi", "cast_ai")]
BASE0 = json.load(open(ROOT / "tuning/B_SETTINGS_PER_PLATFORM.json"))
TONE = json.load(open(ROOT / "tuning/B_SETTINGS_TONE.json"))
DEV, HELD = list(range(101, 131)), list(range(700701, 700731))


def cands(v, c):
    base = BASE0[v][c]
    out = [TONE[v][c], base]
    for h, r, pk, e, vt in itertools.product([24, 96, 240, 960], [0.9, 0.95, 0.99], [0.0, 0.8, 0.85, 0.9, 0.95],
                                             [base.get("early", True), not base.get("early", True)], [base.get("veto", True)]):
        out.append(dict(base, tone=True, tone_H=h, tone_rho=r, pack=pk, early=e, veto=vt))
    return out


def _job(a):
    v, c, s, which = a
    sc = make_scenario(v, s)
    A = gauges(sim_slo.run(sc, c))
    cs = cands(v, c) if which is None else [which]
    return (v, c, s), A, [gauges(sim_slo.run(sc, "omniB:" + c, b_law=BLaw(**x))) for x in cs]


def pick(res, v, c, seeds):
    A = {(v, s): {c: res[(v, c, s)][0]} for s in seeds}
    n = len(res[(v, c, seeds[0])][1])
    best = None
    for i in range(n):
        Bv = {(v, s): {(c, 0): res[(v, c, s)][1][i]} for s in seeds}
        rows = {(v, s): {"A": A[(v, s)][c], "B": Bv[(v, s)][(c, 0)]} for s in seeds}
        L = losses(rows, seeds, "B", "A", v, np.random.default_rng(11))
        g = gains(A, Bv, seeds, v, c, 0)
        key = (len(L), 0 if max(g.values()) >= 1.0 else 1, -(sum(max(0.0, x) for x in g.values()) - 3 * sum(max(0.0, -x) for x in g.values())))
        if best is None or key < best[0]:
            best = (key, i, g, L)
    return best


if __name__ == "__main__":
    LG.TOL = 0.0025
    with Pool(4) as p:
        r = p.map(_job, [(v, c, s, None) for v, c in PAIRS for s in DEV], chunksize=1)
    res = {k: (a, b) for k, a, b in r}
    chosen = {}
    for v, c in PAIRS:
        key, i, g, L = pick(res, v, c, DEV)
        chosen[f"{v}|{c}"] = cands(v, c)[i]
        print("dev", v, c, "losses", len(L), "gain>=1%", key[1] == 0, {m: round(x, 1) for m, x in g.items() if abs(x) >= 0.5}, flush=True)
    pre = {"chosen": chosen, "sha256": hashlib.sha256(json.dumps(chosen, sort_keys=True).encode()).hexdigest(), "heldout_seeds": HELD}
    LG.TOL = 0.005
    with Pool(4) as p:
        r = p.map(_job, [(v, c, s, chosen[f"{v}|{c}"]) for v, c in PAIRS for s in HELD], chunksize=1)
    res = {k: (a, b) for k, a, b in r}
    out = {"preregistration": pre, "heldout": {}}
    for v, c in PAIRS:
        key, i, g, L = pick(res, v, c, HELD)
        out["heldout"][f"{v}|{c}"] = {"losses": L, "gains_pct": g}
        print("heldout", v, c, "losses", [(l["gauge"], round(l["omni_worse_by_pct"], 2)) for l in L],
              {m: round(x, 1) for m, x in g.items() if abs(x) >= 0.5}, flush=True)
    (ROOT / "tuning/B_FIX.json").write_text(json.dumps(out, indent=1))
