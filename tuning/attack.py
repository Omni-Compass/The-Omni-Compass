"""Attack the league's losing cells: evolutionary search of the speed law (with anticipation) per vessel, scored only by
the number of (competitor, gauge) cells where a platform is significantly better than Omni-Compass (tuning/league.py
rule), then by how far behind. Development seeds 101-110 only. The engine equations are unchanged.
Usage: python tuning/attack.py VESSEL GENERATIONS POP SEED [start.json]
"""
from __future__ import annotations

import json, random, sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from omnicompass.speed import SpeedLaw
from tuning.speed_search import gauges
from tuning.league import COMPETITORS, SEEDS, losses

BOUNDS = {"rho0": (0.45, 0.85), "rho_min": (0.35, 0.85), "kI": (0, 0.4), "kE": (0, 0.6), "kq": (0, 1.5),
          "headroom": (0, 0.35), "headroom_up": (0, 0.25), "window": (1, 80), "band": (0, 5), "dwell": (1, 60),
          "after_add": (0, 60), "push_release": (0, 0.2), "cap_idle": (0.7, 1.0), "cap_busy": (0.02, 0.6),
          "antic": (0, 3.0), "antic_lag": (1, 12)}
INTS = {"window", "band", "dwell", "after_add", "antic_lag"}
TOP = {"every": [1, 2, 4], "lat_gain": (0, 3), "slo_mult": (1.1, 3.0)}


def rand_cfg(rng):
    law = {k: (rng.randint(*b) if k in INTS else rng.uniform(*b)) for k, b in BOUNDS.items()}
    law["rho_min"] = min(law["rho_min"], law["rho0"])
    return {"law": law, "every": rng.choice(TOP["every"]), "lat_gain": rng.uniform(*TOP["lat_gain"]),
            "slo_mult": rng.uniform(*TOP["slo_mult"])}


def mutate(cfg, rng, rate=0.3):
    c = json.loads(json.dumps(cfg))
    for k, (lo, hi) in BOUNDS.items():
        if rng.random() < rate:
            if k in INTS:
                c["law"][k] = int(min(hi, max(lo, c["law"][k] + rng.randint(-max(1, (hi - lo) // 8), max(1, (hi - lo) // 8)))))
            else:
                c["law"][k] = float(min(hi, max(lo, c["law"][k] + rng.gauss(0, (hi - lo) * 0.12))))
    c["law"]["rho_min"] = min(c["law"]["rho_min"], c["law"]["rho0"])
    if rng.random() < rate:
        c["every"] = rng.choice(TOP["every"])
    for k in ("lat_gain", "slo_mult"):
        if rng.random() < rate:
            lo, hi = TOP[k]; c[k] = float(min(hi, max(lo, c[k] + rng.gauss(0, (hi - lo) * 0.12))))
    return c


def run_cfg(sc, cfg):
    return gauges(sim_slo.run(sc, "omni_speed", speed_law=SpeedLaw(**cfg["law"]), omni_every=cfg["every"],
                              lat_gain=cfg["lat_gain"], slo_mult=cfg["slo_mult"]))


def _eval(args):
    vessel, cfg = args
    return {s: run_cfg(make_scenario(vessel, s), cfg) for s in SEEDS["dev"]}


def _comp(args):
    vessel, s = args
    sc = make_scenario(vessel, s)
    return s, {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}


def score(vessel, comp, omni):
    rng = np.random.default_rng(11)
    rows = {(vessel, s): dict(comp[s], omni=omni[s]) for s in SEEDS["dev"]}
    L = [l for c in COMPETITORS for l in losses(rows, SEEDS["dev"], "omni", c, vessel, rng)]
    return len(L), sum(min(l["omni_worse_by_pct"], 200.0) for l in L), L


if __name__ == "__main__":
    vessel, gens, pop, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    rng = random.Random(seed)
    starts = json.load(open(sys.argv[5])) if len(sys.argv) > 5 else []
    with Pool(4) as p:
        comp = dict(p.map(_comp, [(vessel, s) for s in SEEDS["dev"]]))
        popn = [c for c in starts] + [rand_cfg(rng) for _ in range(max(0, pop - len(starts)))]
        scored = []
        for g in range(gens):
            res = p.map(_eval, [(vessel, c) for c in popn])
            for c, o in zip(popn, res):
                n, mag, L = score(vessel, comp, o)
                scored.append((n, mag, c, L))
            scored.sort(key=lambda x: (x[0], x[1]))
            scored = scored[:max(4, pop // 3)]
            print(f"gen {g}: best {scored[0][0]} losing cells (magnitude {scored[0][1]:.1f}); "
                  + ", ".join(f"{l['competitor']}:{l['gauge']}+{l['omni_worse_by_pct']:.1f}%" for l in scored[0][3]), flush=True)
            if scored[0][0] == 0:
                break
            elite = [s[2] for s in scored]
            popn = [mutate(rng.choice(elite), rng, rate=rng.choice([0.15, 0.3, 0.5])) for _ in range(pop)]
    best = scored[0]
    out = ROOT / f"tuning/ATTACK_{vessel.upper()}_{seed}.json"
    out.write_text(json.dumps({"vessel": vessel, "losing_cells": best[0], "magnitude": best[1], "config": best[2],
                               "losses": best[3], "elite": [s[2] for s in scored[:8]]}, indent=1))
    print("wrote", out)
