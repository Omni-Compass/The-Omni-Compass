# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Strict architecture C (Omni-Compass sets replicas and machines; Kubernetes only schedules and runs pods): evolutionary
search per vessel on development seeds, scored by losing cells against the seven platforms (tuning/league.py rule).
Usage: python tuning/c_search.py VESSEL GENERATIONS POP SEED"""
import json, random, sys
from multiprocessing import Pool
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import DirectLaw
from omnicompass.speed import SpeedLaw
from tuning.speed_search import gauges
from tuning.league import SEEDS
from tuning.attack import rand_cfg, mutate, _comp, score

DB = {"window": (1, 40), "kb": (0.0, 2.0), "push_release": (0.0, 0.2), "tol": (0.0, 0.15)}


def rand_direct(rng):
    return {"window": rng.randint(*DB["window"]), "kb": rng.uniform(*DB["kb"]), "push_release": rng.uniform(*DB["push_release"]),
            "tol": rng.uniform(*DB["tol"])}


def mut_direct(d, rng, rate):
    d = dict(d)
    for k, (lo, hi) in DB.items():
        if rng.random() < rate:
            d[k] = int(min(hi, max(lo, d[k] + rng.randint(-4, 4)))) if k == "window" else float(min(hi, max(lo, d[k] + rng.gauss(0, (hi - lo) * 0.12))))
    return d


def run_cfg(sc, cfg):
    return gauges(sim_slo.run(sc, "omni_direct", speed_law=SpeedLaw(**cfg["law"]), omni_every=cfg["every"],
                              lat_gain=cfg["lat_gain"], slo_mult=cfg["slo_mult"], direct_law=DirectLaw(**cfg["direct"])))


def _eval(args):
    v, cfg = args
    return {s: run_cfg(make_scenario(v, s), cfg) for s in SEEDS["dev"]}


if __name__ == "__main__":
    v, gens, pop, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    rng = random.Random(seed)
    starts = []
    for f in (ROOT / f"tuning/ATTACK_{v.upper()}_7.json",):
        if f.exists():
            starts = json.load(open(f))["elite"][:6]
    popn = [dict(c, direct=rand_direct(rng)) for c in starts] + [dict(rand_cfg(rng), direct=rand_direct(rng)) for _ in range(pop - len(starts))]
    with Pool(4) as p:
        comp = dict(p.map(_comp, [(v, s) for s in SEEDS["dev"]]))
        scored = []
        for g in range(gens):
            res = p.map(_eval, [(v, c) for c in popn])
            for c, o in zip(popn, res):
                n, mag, L = score(v, comp, o); scored.append((n, mag, c, L))
            scored.sort(key=lambda x: (x[0], x[1])); scored = scored[:max(4, pop // 3)]
            print(f"{v} gen {g}: {scored[0][0]} losing cells (magnitude {scored[0][1]:.0f}) "
                  + ", ".join(f"{l['competitor']}:{l['gauge']}+{l['omni_worse_by_pct']:.0f}%" for l in scored[0][3][:12]), flush=True)
            if scored[0][0] == 0:
                break
            elite = [x[2] for x in scored]
            popn = []
            for _ in range(pop):
                e = rng.choice(elite); r = rng.choice([0.15, 0.3, 0.5])
                popn.append(dict(mutate(e, rng, r), direct=mut_direct(e["direct"], rng, r)))
    b = scored[0]
    (ROOT / f"tuning/C_STRICT_{v.upper()}.json").write_text(json.dumps({"vessel": v, "losing_cells": b[0], "config": b[2], "losses": b[3],
                                                                        "elite": [x[2] for x in scored[:8]]}, indent=1))
