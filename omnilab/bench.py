# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Run a problem-map muscle: every arm on development or held-out seeds, paired comparison against the best native arm.
Usage: python -m omnilab.bench MUSCLE [dev|heldout]"""
from __future__ import annotations

import importlib, json, sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnilab.common import paired

DEV = list(range(1, 9))
HELDOUT = list(range(90001, 90031))


def _one(args):
    name, seed = args
    m = importlib.import_module(f"omnilab.{name}")
    sc = m.scenario(seed)
    return seed, {a: m.run(sc, a) for a in m.ARMS}


def bench(name, which="dev", workers=4):
    m = importlib.import_module(f"omnilab.{name}")
    seeds = DEV if which == "dev" else HELDOUT
    with Pool(workers) as p:
        rows = dict(p.map(_one, [(name, s) for s in seeds]))
    means = {a: {g: float(np.mean([rows[s][a][g] for s in seeds])) for g in m.GAUGES} for a in m.ARMS}
    natives = [a for a in m.ARMS if a.startswith("native")]
    comp = {nat: {om: paired([rows[s][nat] for s in seeds], [rows[s][om] for s in seeds], m.GAUGES)
                  for om in ("omni", "omni_no_engine")} for nat in natives}
    return {"muscle": name, "seeds": seeds, "means": means, "vs": comp}


def show(res):
    m = importlib.import_module(f"omnilab.{res['muscle']}")
    arms = m.ARMS
    print(f"{res['muscle']}  ({len(res['seeds'])} seeds)")
    print(f"  {'gauge':20}" + "".join(f"{a[:16]:>17}" for a in arms))
    for g, direction in m.GAUGES.items():
        print(f"  {g:20}" + "".join(f"{res['means'][a][g]:17.4g}" for a in arms) + f"   ({direction} better)")
    for nat, v in res["vs"].items():
        o = v["omni"]
        print(f"  omni vs {nat}: " + ", ".join(f"{g} {o[g]['better_by']*100:+.1f}% {o[g]['verdict'][0]}" for g in m.GAUGES))


if __name__ == "__main__":
    name = sys.argv[1]; which = sys.argv[2] if len(sys.argv) > 2 else "dev"
    res = bench(name, which)
    out = ROOT / "results" / "muscles" / f"{name.upper()}_{which.upper()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    show(res)
