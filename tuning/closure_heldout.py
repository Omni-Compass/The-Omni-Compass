# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Strict C with the closure law, held-out. The settings chosen on development seeds (tuning/CLOSURE_SEARCH2_DEV.json, else
CLOSURE_SEARCH_DEV.json) are frozen by SHA-256 into tuning/CLOSURE_PREREGISTRATION.json before any held-out run, then run
once on held-out seeds 700201-700230 against the seven platforms (tuning/league.py loss rule).
Usage: python tuning/closure_heldout.py  ->  tuning/CLOSURE_HELDOUT.json"""
import hashlib, json, sys
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
from tuning.league import COMPETITORS, VESSELS, LOWER, HIGHER, losses

SL = dict(rho0=0.7, rho_min=0.7, kI=0.0, kE=0.0)
SEEDS = list(range(700301, 700331))   # fresh held-out set (700201-700230 was spent on the pre-tone settings)
SRC = next(p for p in ("tuning/CLOSURE_FINAL_DEV.json", "tuning/CLOSURE_SEARCH2_DEV.json", "tuning/CLOSURE_SEARCH_DEV.json") if (ROOT / p).exists())
SET = {v: {"closure": d["closure"], "direct": d["direct"], "speed": d.get("speed", SL)} for v, d in json.load(open(ROOT / SRC)).items() if not v.startswith("_")}


def job(a):
    v, s = a
    sc = make_scenario(v, s)
    row = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
    row["omni"] = gauges(sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**SET[v]["speed"]), omni_every=1,
                                     direct_law=DirectLaw(**SET[v]["direct"]), closure_law=ClosureLaw(**SET[v]["closure"])))
    return (v, s), row


if __name__ == "__main__":
    blob = json.dumps(SET, sort_keys=True)
    pre = {"settings_source": SRC, "settings": SET, "sha256": hashlib.sha256(blob.encode()).hexdigest(),
           "closure_py_sha256": hashlib.sha256((ROOT / "omnicompass/closure.py").read_bytes()).hexdigest(), "heldout_seeds": SEEDS}
    (ROOT / "tuning/CLOSURE_PREREGISTRATION.json").write_text(json.dumps(pre, indent=1))
    with Pool(4) as p:
        rows = dict(p.map(job, [(v, s) for v in VESSELS for s in SEEDS]))
    rng = np.random.default_rng(11)
    out = {"preregistration_sha256": pre["sha256"], "seeds": SEEDS, "settings": SET, "attack_list": [], "means": {}}
    for v in VESSELS:
        L = [l for c in COMPETITORS for l in losses(rows, SEEDS, "omni", c, v, rng)]
        out["attack_list"] += L
        out["means"][v] = {a: {m: float(np.mean([rows[(v, s)][a][m] for s in SEEDS])) for m in LOWER + HIGHER}
                           for a in COMPETITORS + ["omni"]}
        print(v, len(L), "losing cells")
        for l in L:
            print(f"    {l['competitor']:13} {l['gauge']:16} omni worse by {l['omni_worse_by_pct']:.1f}%")
    (ROOT / "tuning/CLOSURE_HELDOUT.json").write_text(json.dumps(out, indent=1))
