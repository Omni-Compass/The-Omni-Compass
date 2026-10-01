"""Can Omni-Compass be equal or better than EACH competitor on EVERY gauge? (development seeds 101-110)

Two questions, answered from one search:
  individually  for each competitor and vessel: is there an Omni configuration with no losing gauge against it?
  all at once   for each vessel: is there one Omni configuration with no losing gauge against every competitor?
Candidate Omni configurations: the frozen fleet-law family with free constants, and the speed-law family
(omnicompass/speed.py); the engine equations are unchanged. A loss is as in tuning/league.py (worse beyond 0.5% and the
paired bootstrap 95% interval excludes zero).
Usage: python tuning/dominate.py N SEED
"""
from __future__ import annotations

import json, random, sys
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from omnicompass.adapter import mode_law
from omnicompass.speed import SpeedLaw
from tuning.speed_search import gauges, LOWER, HIGHER
from tuning.league import COMPETITORS, VESSELS, SEEDS, losses

KEYS = [(v, s) for v in VESSELS for s in SEEDS["dev"]]


def sample(rng, i):
    if i % 2 == 0:
        rho0 = rng.uniform(0.50, 0.80)
        return {"family": "speed", "law": dict(rho0=rho0, rho_min=rng.uniform(0.40, rho0), kI=rng.uniform(0, 0.3),
                kE=rng.uniform(0, 0.5), kq=rng.uniform(0.0, 1.0), headroom=rng.uniform(0.0, 0.3),
                headroom_up=rng.uniform(0.0, 0.2), window=rng.randint(1, 60), band=rng.randint(1, 4),
                dwell=rng.randint(1, 40), after_add=rng.randint(0, 40), push_release=rng.uniform(0.0, 0.15),
                cap_idle=rng.uniform(0.7, 1.0), cap_busy=rng.uniform(0.05, 0.5)),
                "every": rng.choice([1, 2, 4]), "lat_gain": rng.uniform(0, 3), "slo_mult": rng.uniform(1.1, 3.0)}
    rho0 = rng.uniform(0.55, 0.95)
    return {"family": "fleet", "law": dict(rho0=rho0, rho_min=rng.uniform(0.40, rho0), kI=rng.uniform(0, 0.3),
            kE=rng.uniform(0, 0.5), kq=rng.uniform(0.2, 1.5), down_band=rng.randint(0, 4), down_dwell=rng.randint(1, 20),
            down_after_add=rng.randint(0, 20), push_release=rng.uniform(0.01, 0.12), cap_min=rng.uniform(0.65, 1.0),
            margin=rng.uniform(0, 0.3), U_gate=rng.uniform(0.4, 0.95), up_max=rng.choice([2, 4, 8])),
            "every": rng.choice([1, 2, 4]), "lat_gain": rng.uniform(0, 3), "slo_mult": rng.uniform(1.1, 3.0)}


def run_cfg(sc, cfg):
    if cfg["family"] == "speed":
        r = sim_slo.run(sc, "omni_speed", speed_law=SpeedLaw(**cfg["law"]), omni_every=cfg["every"],
                        lat_gain=cfg["lat_gain"], slo_mult=cfg["slo_mult"])
    else:
        r = sim_slo.run(sc, "omni_fleet", governor_law=replace(mode_law("throughput"), **cfg["law"]),
                        omni_every=cfg["every"], lat_gain=cfg["lat_gain"], slo_mult=cfg["slo_mult"])
    return gauges(r)


def _cfg_job(args):
    i, cfg = args
    return i, {k: run_cfg(make_scenario(*k), cfg) for k in KEYS}


def _comp_job(k):
    sc = make_scenario(*k)
    return k, {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}


def slim(g):
    return {m: float(g[m]) for m in LOWER + HIGHER}


if __name__ == "__main__":
    n, seed = int(sys.argv[1]), int(sys.argv[2])
    rng = random.Random(seed)
    cfgs = {i: sample(rng, i) for i in range(n)}
    with Pool(4) as p:
        comp = dict(p.map(_comp_job, KEYS))
        res = dict(p.map(_cfg_job, list(cfgs.items()), chunksize=2))
    brng = np.random.default_rng(11)
    out = {"cfgs": cfgs, "individual": {}, "all_at_once": {}}
    for v in VESSELS:
        seeds = SEEDS["dev"]
        per = {}
        for i in cfgs:
            rows = {(v, s): dict(comp[(v, s)], omni=res[i][(v, s)]) for s in seeds}
            per[i] = {c: losses(rows, seeds, "omni", c, v, brng) for c in COMPETITORS}
        for c in COMPETITORS:
            best = min(per, key=lambda i: (len(per[i][c]), sum(l["omni_worse_by_pct"] for l in per[i][c])))
            out["individual"][f"{v}|{c}"] = {"config": best, "losses": per[best][c]}
        tot = {i: sum(len(per[i][c]) for c in COMPETITORS) for i in per}
        best = min(tot, key=tot.get)
        out["all_at_once"][v] = {"config": best, "n_losses": tot[best], "losses": [l for c in COMPETITORS for l in per[best][c]]}
    (ROOT / f"tuning/DOMINATE_{seed}.json").write_text(json.dumps(out, indent=1, default=str))
    print("INDIVIDUALLY (best Omni configuration against each competitor alone):")
    for k, r in out["individual"].items():
        print(f"  {k:24} config {r['config']:>4}: " + (", ".join(f"{l['gauge']} +{l['omni_worse_by_pct']:.1f}%" for l in r["losses"]) or "NO LOSING GAUGE"))
    print("ALL AT ONCE (one Omni configuration per vessel against every competitor):")
    for v, r in out["all_at_once"].items():
        print(f"  {v:6} config {r['config']}: {r['n_losses']} losing cells")
