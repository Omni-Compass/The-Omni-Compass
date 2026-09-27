"""Confirmatory run. The single global closure-law setting frozen in tuning/GLOBAL_LEAGUE_PREREGISTRATION.json is run
once on 100 never-used scenarios per workload (seeds 710001-710100) against the seven platforms, every gauge. For each
of the 364 (workload x platform x gauge) cells: the paired mean difference, its bootstrap distribution (10,000
resamples), a two-sided bootstrap p-value, and the Holm-Bonferroni step-down correction across all 364 cells at family
alpha 0.05. A cell is reported better / worse only if it survives the correction and the difference exceeds the 0.5%
practical tolerance (0.5 events for counts); otherwise it is equal. Every earlier held-out round is listed in the output
with its seed range. Usage: python tuning/confirmatory.py  ->  tuning/CONFIRMATORY.json

--coord: the same frozen setting with the nervous-system coordination switched on (ClosureLaw coord=True: pods are
stepped first, a machine move opposite to the pod move is vetoed). Fresh seeds 712001-712100, frozen in
tuning/COORD_PREREGISTRATION.json (setting, seeds, SHA-256 of the code) before the first scenario runs. Same 364 cells,
same Holm correction; controller contradictions per arm reported beside the family (not added to it).
->  tuning/CONFIRMATORY_COORD.json"""
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
from tuning.league import COMPETITORS, VESSELS, LOWER, HIGHER, COUNTS, TOL

PRE = json.load(open(ROOT / "tuning/GLOBAL_LEAGUE_PREREGISTRATION.json"))
SET = PRE["setting"]
COORD = "--coord" in sys.argv
SEEDS = list(range(712001, 712101)) if COORD else list(range(710001, 710101))
ROUNDS = {"LEAGUE_HELDOUT (first C)": "700101-700130", "B held-out": "700101-700130 / 700201-700230",
          "closure pre-tone": "700201-700230", "closure muscle tone": "700301-700330", "B second generation": "700401-700430",
          "C vs incumbent": "700501-700530", "C vs incumbent wide": "700601-700630", "B fix": "700701-700730",
          "C vs incumbent round 3": "700801-700830", "C calm round": "700901-700930", "site league": "701001-701030",
          "self-calibrating law (not run held-out)": "702001-702030", "global setting": "703001-703030",
          "PlanetLab real traces": "704001-704030", "protocol faults": "900001-900100", "confirmatory": "710001-710100", "confirmatory with coordination": "712001-712100"}


def job(a):
    v, s = a
    sc = make_scenario(v, s)
    row, contra = {}, {}
    for c in COMPETITORS:
        r = sim_slo.run(sc, c); row[c] = gauges(r); contra[c] = r.get("contradictions", 0)
    cl = dict(SET["closure"], site=(v == "multi"), **({"coord": True} if COORD else {}))
    r = sim_slo.run(sc, "omni_closure", speed_law=SpeedLaw(**SET["speed"]), omni_every=1,
                    direct_law=DirectLaw(**SET["direct"]), closure_law=ClosureLaw(**cl))
    row["omni"] = gauges(r); contra["omni"] = r.get("contradictions", 0)
    return (v, s), (row, contra)


def preregister():
    import hashlib, datetime
    f = ROOT / "tuning/COORD_PREREGISTRATION.json"
    if f.exists():
        return json.loads(f.read_text())
    code = {k: hashlib.sha256((ROOT / k).read_bytes()).hexdigest() for k in
            ("omnicompass/closure.py", "fleet/sim_slo.py", "tuning/confirmatory.py", "tuning/GLOBAL_LEAGUE_PREREGISTRATION.json")}
    rec = {"setting": SET, "coord": True, "seeds": [SEEDS[0], SEEDS[-1]], "cells": "7 platforms x 4 workloads x 13 gauges = 364",
           "rule": "Holm-Bonferroni at family alpha 0.05 and the 0.5% practical tolerance, as tuning/CONFIRMATORY.json",
           "code_sha256": code, "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    f.write_text(json.dumps(rec, indent=1)); return rec


if __name__ == "__main__":
    if COORD:
        preregister()
    with Pool(4) as p:
        both = dict(p.map(job, [(v, s) for v in VESSELS for s in SEEDS], chunksize=2))
    rows = {k: v[0] for k, v in both.items()}
    contradictions = {v: {c: float(np.mean([both[(v, s)][1][c] for s in SEEDS])) for c in COMPETITORS + ["omni"]} for v in VESSELS}
    rng = np.random.default_rng(20260927)
    cells = []
    for v in VESSELS:
        for c in COMPETITORS:
            for m in LOWER + HIGHER:
                a = np.array([rows[(v, s)][c][m] for s in SEEDS]); b = np.array([rows[(v, s)]["omni"][m] for s in SEEDS])
                d = (a - b) if m in LOWER else (b - a)          # positive = Omni better
                bs = d[rng.integers(0, len(d), (10000, len(d)))].mean(1)
                p = float(min(1.0, 2 * min((bs <= 0).mean(), (bs >= 0).mean())))
                scale = max(abs(a.mean()), 1e-9)
                cells.append({"vessel": v, "competitor": c, "gauge": m, "platform": float(a.mean()), "omni": float(b.mean()),
                              "omni_better_by_pct": float(d.mean() / scale * 100), "p": p,
                              "practical": bool(abs(d.mean()) > (0.5 if m in COUNTS else TOL * scale))})
    order = sorted(range(len(cells)), key=lambda i: cells[i]["p"]); m = len(cells); stop = False
    for k, i in enumerate(order):                      # Holm-Bonferroni step-down
        thr = 0.05 / (m - k)
        cells[i]["holm_significant"] = (not stop) and cells[i]["p"] <= thr
        stop = stop or not cells[i]["holm_significant"]
    for c_ in cells:
        c_["verdict"] = ("better" if c_["omni_better_by_pct"] > 0 else "worse") if (c_["holm_significant"] and c_["practical"]) else "equal"
    from collections import Counter
    tally = Counter(c_["verdict"] for c_ in cells)
    per = {v: dict(Counter(c_["verdict"] for c_ in cells if c_["vessel"] == v)) for v in VESSELS}
    out = {"setting": SET, "preregistration_sha256": PRE["sha256"], "seeds": [SEEDS[0], SEEDS[-1]], "tally": dict(tally), "per_workload": per,
           "held_out_rounds": ROUNDS, "cells": cells}
    if COORD:
        out["coord"] = True; out["contradictions_mean_per_day"] = contradictions
    (ROOT / ("tuning/CONFIRMATORY_COORD.json" if COORD else "tuning/CONFIRMATORY.json")).write_text(json.dumps(out, indent=1))
    print("confirmatory" + (" with coordination" if COORD else "") + ", 100 scenarios per workload, Holm-corrected:", dict(tally))
    if COORD:
        for v in VESSELS:
            print("  contradictions", v, {k: round(x, 2) for k, x in contradictions[v].items()})
    for v in VESSELS:
        print(" ", v, per[v], [(c_["competitor"], c_["gauge"], round(c_["omni_better_by_pct"], 1)) for c_ in cells if c_["vessel"] == v and c_["verdict"] == "worse"])
