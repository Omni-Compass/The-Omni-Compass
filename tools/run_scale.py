#!/usr/bin/env python3
"""Six organisms, native and Omni, over many runs and at many sizes (evidence class S: the realm models).

  1 Compute / AI / Cloud              (345 muscles)
  2 Physics / Robotics / Autonomous   (262)
  3 Energy / Facility / Industrial    (282)
  4 Distribution / Specialized        (337)
  5 the four stacked, every duplicate kept (1,226), one body on one clock
  6 the whole tower, every muscle once (656)

Every organism runs native (its own controllers) and omni (the bowl law on every muscle, realms/bowl_arm.py) on the
same seed; --runs paired seeds (7000 on); --scale copies of the organism on one clock (each copy its own seeds), so
10x is ten clusters of that organism governed together. Receipts: per organism, work per energy, work, energy and
violations with their 95% intervals over runs, the label by the round-3 rule, and the raw per-run contrasts.

  python3 tools/run_scale.py --runs 100 --scale 1 --out results/scale/r100-x1 [--workers N] [--organisms 1,2,5]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realms.harness import catalog, run_organism_arm, paired_organism, summarize, label  # noqa: E402

REALMS = ("compute_ai_cloud", "physics_robotics_autonomous", "energy_facility_industrial", "distribution_specialized")
ORGS = {"1": ("compute_ai_cloud", "Compute / AI / Cloud"), "2": ("physics_robotics_autonomous", "Physics / Robotics / Autonomous"),
        "3": ("energy_facility_industrial", "Energy / Facility / Industrial"), "4": ("distribution_specialized", "Distribution / Specialized"),
        "5": ("stack_1226", "The four stacked, duplicates kept"), "6": ("tower_656", "The whole tower, every muscle once")}
SEED0 = 7000


def rows_for(key, scale):
    rows = catalog()
    if key == "stack_1226":
        base = [dict(r, muscle_id=f"{r['muscle_id']}@{realm}") for realm in REALMS for r in rows if realm in r["realms"].split(";")]
    elif key == "tower_656":
        base = rows
    else:
        base = [r for r in rows if key in r["realms"].split(";")]
    return [dict(r, muscle_id=r["muscle_id"] + (f"~{c}" if c else "")) for c in range(scale) for r in base]


def job(args):
    key, scale, seed = args
    rows = rows_for(key, scale)
    nat = run_organism_arm(rows, seed, "native")
    om = run_organism_arm(rows, seed, "bowl")
    c = paired_organism(om, nat)
    c["restore_ok"] = om["restore_ok"]
    c["energy_native_j"] = sum(p["energy_j"] for p in nat["plants"])
    c["energy_omni_j"] = sum(p["energy_j"] for p in om["plants"])
    return key, seed, c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--organisms", default="1,2,3,4,5,6")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    keys = [ORGS[k][0] for k in a.organisms.split(",")]
    jobs = [(k, a.scale, SEED0 + i) for i in range(a.runs) for k in keys]
    t0 = time.time()
    res = {k: {} for k in keys}
    with ProcessPoolExecutor(a.workers) as ex:
        for n, (k, seed, c) in enumerate(ex.map(job, jobs, chunksize=1), 1):
            res[k][seed] = c
            if n % max(1, len(jobs) // 20) == 0:
                print(f"{n}/{len(jobs)} done, {time.time() - t0:.0f} s", flush=True)
    commit = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    names = {v[0]: v[1] for v in ORGS.values()}
    L = [f"# Six organisms, {a.runs} runs, {a.scale}x size", "",
         f"Evidence class **S** (models). Commit `{commit[:12]}`, seeds {SEED0}-{SEED0 + a.runs - 1}, {a.scale} cop{'y' if a.scale == 1 else 'ies'} "
         f"of each organism on one clock, {time.time() - t0:.0f} s on {a.workers} workers. Native: each organism's own "
         "controllers. Omni: the bowl law on every muscle (`realms/bowl_arm.py`). Harness `tools/run_scale.py`.", "",
         "Band first (the founder's rule): no win unless the time over the service line is no higher than native's "
         "(violations, mean over runs, at or under 0 pp).", "",
         "| # | Organism | Muscles | Label | Band first | Work per energy | Work | Energy | Violations (pp) | Knobs handed back |",
         "|---|---|---:|---|---|---:|---:|---:|---:|---|"]
    summary = {}
    for num, (k, nm) in ORGS.items():
        if k not in res:
            continue
        per = [res[k][s] for s in sorted(res[k])]
        sm = summarize(per)
        lab = label(per, valid=all(c["restore_ok"] for c in per))
        summary[k] = {"label": lab, **{q: list(v) for q, v in sm.items()}, "runs": len(per)}
        f = lambda q, s=100.0, u="%": f"{s * sm[q][0]:+.3f}{u} ({s * sm[q][1]:+.3f} to {s * sm[q][2]:+.3f})"
        band = "held" if sm["viol_pp"][0] <= 0.0 else "NOT held"
        summary[k]["band_first"] = band
        L.append(f"| {num} | {nm} | {len(rows_for(k, a.scale))} | **{lab}** | {band} | {f('primary')} | {f('work')} | {f('energy')} | "
                 f"{f('viol_pp', 1.0, '')} | {all(c['restore_ok'] for c in per)} |")
    (out / "SCALE.md").write_text("\n".join(L) + "\n")
    (out / "SCALE.json").write_text(json.dumps({"runs": a.runs, "scale": a.scale, "commit": commit, "summary": summary,
                                                "per_run": {k: {str(s): c for s, c in v.items()} for k, v in res.items()}}) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
