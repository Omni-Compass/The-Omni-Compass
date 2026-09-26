"""League table: every competitor against Omni-Compass, one at a time, on every gauge and every vessel.

Rule (the owner's): Omni-Compass must be equal or better than EACH competitor on EACH gauge. A cell is a loss when the
competitor is better by more than the tolerance AND the paired bootstrap 95% interval excludes zero. Every loss goes on
the attack list.

Competitors, each at its documented defaults (fleet plant with response time, fleet/sim_slo.py; vendor arms emulate
documented behaviour, not the vendors' binaries):
  k8s_hpa70_ca   Kubernetes: HPA (70%, the target of every earlier study) + Cluster Autoscaler (= GKE balanced)
  openshift, gke_optimize, aks_nap (= Karpenter, also EKS Auto Mode), turbonomic, cast_ai, spot_ocean
Omni-Compass: one configuration per vessel type (web, multi, batch, gpu), chosen from the candidates below as the one with
the fewest losses on the development seeds. The operator declaring the vessel type is a human-set boundary.
Usage: python tuning/league.py [dev|heldout] [candidates.json]
"""
from __future__ import annotations

import json, sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from omnicompass.speed import SpeedLaw
from tuning.speed_search import gauges, LOWER, HIGHER, COUNTS

COMPETITORS = ["k8s_hpa70_ca", "openshift", "gke_optimize", "aks_nap", "turbonomic", "cast_ai", "spot_ocean"]
SENSITIVITY = ["k8s_hpa50_ca", "k8s_hpa60_ca", "k8s_hpa80_ca"]   # other Kubernetes HPA targets: reported, not opponents
VESSELS = ("web", "multi", "batch", "gpu")
SEEDS = {"dev": list(range(101, 111)), "heldout": list(range(700101, 700131))}
TOL = 0.005


def candidates(path=None):
    c = {"omni_fleet": None}
    R = {r["i"]: r["cfg"] for r in json.load(open(ROOT / "tuning/SPEED_SEARCH_21.json"))}
    for i in (159, 176, 169, 149, 112, 188, 166):
        c[f"speed{i}"] = R[i]
    if path:
        c.update(json.load(open(path)))
    return c


def run_arm(sc, name, cfg):
    if name in COMPETITORS:
        return gauges(sim_slo.run(sc, name))
    if cfg is None:
        return gauges(sim_slo.run(sc, "omni_fleet"))
    return gauges(sim_slo.run(sc, "omni_speed", speed_law=SpeedLaw(**cfg["law"]), omni_every=cfg["every"],
                              lat_gain=cfg["lat_gain"], slo_mult=cfg["slo_mult"]))


def _job(args):
    v, s, cands = args
    sc = make_scenario(v, s)
    out = {a: run_arm(sc, a, None) for a in COMPETITORS}
    out.update({n: run_arm(sc, n, c) for n, c in cands.items()})
    return (v, s), out


def losses(rows, seeds, omni, comp, v, rng):
    L = []
    for m in LOWER + HIGHER:
        a = np.array([rows[(v, s)][comp][m] for s in seeds]); b = np.array([rows[(v, s)][omni][m] for s in seeds])
        d = (b - a) if m in LOWER else (a - b)            # positive = Omni worse
        scale = max(abs(a.mean()), 1e-9)
        if d.mean() <= TOL * scale + (0.5 if m in COUNTS else 1e-9):
            continue
        bs = d[rng.integers(0, len(d), (3000, len(d)))].mean(1)
        if np.percentile(bs, 2.5) > 0:
            L.append({"vessel": v, "competitor": comp, "gauge": m, "competitor_value": float(a.mean()),
                      "omni_value": float(b.mean()), "omni_worse_by_pct": float(d.mean() / scale * 100)})
    return L


def league(which="dev", extra=None, workers=4):
    cands = candidates(extra)
    seeds = SEEDS[which]
    with Pool(workers) as p:
        rows = dict(p.map(_job, [(v, s, cands) for v in VESSELS for s in seeds], chunksize=1))
    rng = np.random.default_rng(11)
    pick, table = {}, {}
    for v in VESSELS:
        per = {n: [l for c in COMPETITORS for l in losses(rows, seeds, n, c, v, rng)] for n in cands}
        best = min(per, key=lambda n: (len(per[n]), sum(l["omni_worse_by_pct"] for l in per[n])))
        pick[v] = best; table[v] = per[best]
    means = {v: {a: {m: float(np.mean([rows[(v, s)][a][m] for s in seeds])) for m in LOWER + HIGHER}
                 for a in COMPETITORS + [pick[v]]} for v in VESSELS}
    return {"seeds": which, "omni_per_vessel": pick, "attack_list": [l for v in VESSELS for l in table[v]], "means": means}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    res = league(which, sys.argv[2] if len(sys.argv) > 2 else None)
    (ROOT / f"tuning/LEAGUE_{which.upper()}.json").write_text(json.dumps(res, indent=1))
    print("Omni configuration per vessel:", res["omni_per_vessel"])
    print(f"attack list: {len(res['attack_list'])} cells where a competitor beats Omni")
    for l in sorted(res["attack_list"], key=lambda l: (l["vessel"], l["gauge"], -l["omni_worse_by_pct"])):
        print(f"  {l['vessel']:6} {l['gauge']:18} {l['competitor']:14} competitor {l['competitor_value']:.4g}  omni {l['omni_value']:.4g}  "
              f"(omni worse by {l['omni_worse_by_pct']:.1f}%)")
