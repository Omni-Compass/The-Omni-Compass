# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""What each mechanism contributes. The confirmatory setting (tuning/GLOBAL_LEAGUE_PREREGISTRATION.json) against
versions with one mechanism removed, on 30 fresh scenarios per workload (seeds 711001-711030), paired:
  gate_off      the six-state engine's equation-(2) push no longer gates releases (push_release = infinity)
  no_turn       releases no longer wait for the turning point (Chapters 29-30)
  no_tone       released machines are powered off instead of parked (no warm reserve)
  no_trend      the dual bath's rate is removed (b = 0: level only, no forecast of the trend)
  no_closure    the closure law is removed; machines follow the engine-driven speed governor (the earlier C)
Reported: mean change of every gauge against the full law (positive = the removal made it worse) with a paired 95%
bootstrap interval, plus contradictions (controllers fighting, quick reversals). Usage: python tuning/ablation.py"""
import json, sys
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
from tuning.league import VESSELS, LOWER, HIGHER, candidates, run_arm

SET = json.load(open(ROOT / "tuning/GLOBAL_LEAGUE_PREREGISTRATION.json"))["setting"]
PICK = json.load(open(ROOT / "tuning/LEAGUE_HELDOUT.json"))["omni_per_vessel"]; CANDS = candidates()
SEEDS = list(range(711001, 711031))
VAR = {"full": {}, "gate_off": {"push_release": 1e9}, "no_turn": {"turn": False}, "no_tone": {"tone": False}, "no_trend": {"b": 0.0}}
G = LOWER + HIGHER + ["contradictions"]


def job(a):
    v, s = a
    sc = make_scenario(v, s); row = {}
    for nm, ch in VAR.items():
        cl = dict(SET["closure"], site=(v == "multi"), **ch)
        row[nm] = gauges(sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**SET["speed"]), omni_every=1,
                                     direct_law=DirectLaw(**SET["direct"]), closure_law=ClosureLaw(**cl)))
    row["no_closure"] = run_arm(sc, PICK[v], CANDS[PICK[v]])
    row["kubernetes"] = gauges(sim_slo.run(sc, "k8s_hpa70_ca"))
    return (v, s), row


if __name__ == "__main__":
    with Pool(4) as p:
        rows = dict(p.map(job, [(v, s) for v in VESSELS for s in SEEDS], chunksize=1))
    rng = np.random.default_rng(3); out = {}
    for v in VESSELS:
        out[v] = {}
        for nm in list(VAR)[1:] + ["no_closure", "kubernetes"]:
            out[v][nm] = {}
            for g in G:
                f = np.array([rows[(v, s)]["full"].get(g, 0.0) for s in SEEDS]); x = np.array([rows[(v, s)][nm].get(g, 0.0) for s in SEEDS])
                d = (x - f) if g not in HIGHER else (f - x)            # positive = removing it made things worse
                bs = d[rng.integers(0, len(d), (4000, len(d)))].mean(1)
                sc = max(abs(f.mean()), 1e-9)
                out[v][nm][g] = {"worse_by_pct": float(d.mean() / sc * 100), "ci": [float(np.percentile(bs, 2.5) / sc * 100), float(np.percentile(bs, 97.5) / sc * 100)]}
        print(v)
        for nm in out[v]:
            sig = {g: round(x["worse_by_pct"], 1) for g, x in out[v][nm].items() if (x["ci"][0] > 0 or x["ci"][1] < 0) and abs(x["worse_by_pct"]) >= 0.5}
            print(f"   remove {nm:11}", sig, flush=True)
    (ROOT / "tuning/ABLATION.json").write_text(json.dumps({"seeds": [SEEDS[0], SEEDS[-1]], "variants": VAR, "result": out}, indent=1))
