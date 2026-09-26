"""Speed-first fleet mode: random search on development seeds only (101-104 of every vessel).

Rule, fixed before the search: against HPA 0.7 + Cluster Autoscaler, in EVERY development scenario, NO gauge may be
worse (tolerance 0.5% on continuous gauges, 0 on counts). Among configurations that pass, pick the one whose
worst gauge-mean improvement (over gauges that can still improve) is largest. Engine equations are unchanged:
only law constants and the response-time nerve (lat_gain, slo_mult) are searched.
Usage: python tuning/speed_search.py N SEED
"""
import json, random, sys
from multiprocessing import Pool
from pathlib import Path
from dataclasses import replace
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet.harness import make_scenario
from fleet import sim_slo
from omnicompass.adapter import mode_law
from omnicompass.speed import SpeedLaw

VESSELS = ("web", "multi", "batch", "gpu")
DEV = [(v, s) for v in VESSELS for s in (101, 102, 103, 104)]
LOWER = ["energy_kwh", "p95_ms", "p99_ms", "mean_ms", "violation_backlog", "violation_power", "violation_heat",
         "start_stop", "node_reversals", "node_hours", "pod_changes"]
HIGHER = ["work_completed", "time_healthy"]
COUNTS = {"start_stop", "node_reversals", "pod_changes"}
BASE_ARM = "k8s_hpa70_ca"


def gauges(r):
    r = dict(r); r["start_stop"] = r["machines_started"] + r["machines_stopped"]; return r


def rel(m, b, o):
    """Improvement as a fraction of the baseline (positive = better)."""
    if m in HIGHER:
        return (o - b) / max(abs(b), 1e-9)
    return (b - o) / max(abs(b), 1e-9) if b > 1e-12 else (0.0 if o <= 1e-12 else -1.0)


def worse(m, b, o):
    if m in COUNTS:
        return o > b
    if m in HIGHER:
        return o < b - 0.005 * abs(b) - 1e-9
    return o > b + 0.005 * abs(b) + 1e-9


def evaluate(cfg, keys=DEV, base=None):
    rows = {k: gauges(sim_slo.run(make_scenario(*k), "omni_speed", speed_law=SpeedLaw(**cfg["law"]), omni_every=cfg["every"],
                                  lat_gain=cfg["lat_gain"], slo_mult=cfg["slo_mult"])) for k in keys}
    bad = [(k, m) for k in keys for m in LOWER + HIGHER if worse(m, base[k][m], rows[k][m])]
    mean_rel = {m: float(np.mean([rel(m, base[k][m], rows[k][m]) for k in keys])) for m in LOWER + HIGHER}
    return rows, bad, mean_rel


def sample(rng):
    rho0 = rng.uniform(0.50, 0.75)
    return {"law": dict(rho0=rho0, rho_min=rng.uniform(0.40, rho0), kI=rng.uniform(0, 0.3), kE=rng.uniform(0, 0.5),
                        kq=rng.uniform(0.0, 1.0), headroom=rng.uniform(0.0, 0.3), headroom_up=rng.uniform(0.0, 0.2),
                        window=rng.randint(1, 60), band=rng.randint(1, 4), dwell=rng.randint(1, 40),
                        after_add=rng.randint(0, 40), push_release=rng.uniform(0.0, 0.15),
                        cap_idle=rng.uniform(0.7, 1.0), cap_busy=rng.uniform(0.05, 0.5)),
            "every": rng.choice([1, 2, 4]), "lat_gain": rng.uniform(0, 3), "slo_mult": rng.uniform(1.1, 3.0)}


def _job(args):
    i, cfg, base = args
    _, bad, mr = evaluate(cfg, DEV, base)
    return {"i": i, "cfg": cfg, "n_worse": len(bad), "worse": sorted({m for _, m in bad}), "mean_rel": mr}


def baseline(keys=DEV):
    return {k: gauges(sim_slo.run(make_scenario(*k), BASE_ARM)) for k in keys}


def score(r, base):
    """Worst mean improvement over gauges not already at their floor in every development scenario."""
    live = [m for m in LOWER + HIGHER if any((base[k][m] > 1e-12 if m in LOWER else base[k][m] < 0.9999) for k in DEV)]
    return min(r["mean_rel"][m] for m in live)


if __name__ == "__main__":
    n, seed = int(sys.argv[1]), int(sys.argv[2])
    base = baseline()
    rng = random.Random(seed)
    jobs = [(i, sample(rng), base) for i in range(n)]
    with Pool(4) as p:
        res = p.map(_job, jobs, chunksize=4)
    for r in res:
        r["score"] = score(r, base)
    out = ROOT / f"tuning/SPEED_SEARCH_{seed}.json"
    out.write_text(json.dumps(res, indent=1))
    ok = [r for r in res if r["n_worse"] == 0]
    print("configs", len(res), "with no gauge worse anywhere:", len(ok))
    for r in sorted(res, key=lambda r: (r["n_worse"], -r["score"]))[:8]:
        print(r["i"], r["n_worse"], r["worse"], round(r["score"], 3), {m: round(v, 3) for m, v in r["mean_rel"].items()})
