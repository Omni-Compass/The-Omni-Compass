#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The six organisms' full grid, built from the saved receipts (results/scale/receipts/round6-<size>x.md, each the
printed receipt of one GitHub `six` run): 6 organisms x sizes 1, 10, 100, 1,000 clusters x runs 1, 10, 100, 1,000.

    python3 tools/grid.py        writes results/scale/GRID.md

A cell whose receipt is not saved yet reads "running"; 1,000 runs at 1,000 clusters reads "not run" (about 6,000
machine-hours, beyond the machines available). How to read every table: docs/HOW_TO_READ_THE_RESULTS.md.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "results" / "scale" / "receipts"
OUT = ROOT / "results" / "scale" / "GRID.md"
SIZES, RUNS = (1, 10, 100, 1000), (1, 10, 100, 1000)
ORGS = ["Compute / AI / Cloud", "Physics / Robotics / Autonomous", "Energy / Facility / Industrial",
        "Distribution / Specialized", "The four stacked, duplicates kept", "The whole tower, every muscle once"]
MUSCLES = {"Compute / AI / Cloud": 345, "Physics / Robotics / Autonomous": 262, "Energy / Facility / Industrial": 282,
           "Distribution / Specialized": 337, "The four stacked, duplicates kept": 1226,
           "The whole tower, every muscle once": 656}
COLS = {"label": 4, "band": 5, "wpe": 6, "work": 7, "energy": 8, "viol": 9, "knobs": 10}


def parse(path):
    """{(runs, organism): {column: text}} and the receipt's source line."""
    cells, runs, source = {}, None, ""
    for line in path.read_text().splitlines():
        m = re.match(r"## (\d+) runs?$", line.strip())
        if m:
            runs = int(m.group(1)); continue
        if line.startswith("Source:"):
            source = line[len("Source:"):].strip()
        if runs and line.startswith("| ") and not line.startswith("| #") and not line.startswith("|---"):
            f = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(f) >= 11 and f[1] in MUSCLES:
                cells[(runs, f[1])] = {k: f[i] for k, i in COLS.items()}
    return cells, source


def main():
    data, sources = {}, {}
    for sc in SIZES:
        p = REC / f"round6-{sc}x.md"
        if p.exists():
            data[sc], sources[sc] = parse(p)

    def cell(sc, r, org, k):
        if sc == 1000 and r == 1000:
            return "not run"
        c = data.get(sc, {}).get((r, org))
        if c is None:
            return "running"
        v = c[k]
        return v.split(" (")[0] if k in ("wpe", "work", "energy", "viol") else v

    head = "| Organism (muscles) | " + " | ".join(f"{sc}x, {r} run{'s' if r > 1 else ''}" for sc in SIZES for r in RUNS) + " |"
    rule = "|---|" + "---:|" * (len(SIZES) * len(RUNS))
    L = ["# The six organisms: the full grid", "",
         "Evidence class **S** (models of the plants, not hardware). Every organism runs native (its own controllers) "
         "and native with Omni-Compass on top (the bowl law on every muscle, round 6 of `docs/REALMS_PREREGISTRATION.md`) "
         "on the same seed, the same load and the same clock. **Size** is the number of copies of the organism governed "
         "together on one clock: 1, 10, 100 and 1,000 clusters. **Runs** are paired seeds from 7000 on; 1, 10, 100 and "
         "1,000 runs are the first N of the same set, so each block nests inside the next. Built by `tools/grid.py` from "
         "the saved receipts in `results/scale/receipts/`. How to read it: `docs/HOW_TO_READ_THE_RESULTS.md`.", "",
         "Sources:"] + [f"- {sc}x: {sources[sc]}" if sc in sources else f"- {sc}x: running on GitHub" for sc in SIZES] + [
         "- 1,000 runs at 1,000 clusters is not run: about 6,000 machine-hours, beyond the machines available.", ""]
    for k, title, note in (("wpe", "Work per energy, with Omni-Compass on top against native", "higher is better"),
                           ("energy", "Energy, with Omni-Compass on top against native", "lower is better"),
                           ("viol", "Time over the service line, with Omni-Compass on top minus native (percentage points)",
                            "lower is better; band first holds where it is at or under 0"),
                           ("work", "Work done, with Omni-Compass on top against native", "equal is the guardrail"),
                           ("label", "Label by the preregistered rule", "chosen by code, never by hand")):
        L += [f"## {title} ({note})", "", head, rule]
        for org in ORGS:
            L.append(f"| {org} ({MUSCLES[org]}) | " + " | ".join(cell(sc, r, org, k).replace("**", "")
                                                                 for sc in SIZES for r in RUNS) + " |")
        L.append("")
    done = [(sc, r, o) for sc in data for (r, o) in data[sc]]
    knobs = all(data[sc][(r, o)]["knobs"] == "True" for sc, r, o in done)
    held = sum(1 for sc, r, o in done if data[sc][(r, o)]["band"] == "held")
    L += ["## Summary of the completed cells", "",
          f"- Cells completed: {len(done)} of {len(SIZES) * len(RUNS) * len(ORGS) - len(ORGS)} (six organisms x 15 size and run cells).",
          f"- Band first held: {held} of {len(done)}.",
          f"- Every knob handed back in every completed cell: {knobs}.",
          "- The full receipt of each size, with the 95% interval of every number, is in `results/scale/receipts/`."]
    OUT.write_text("\n".join(L) + "\n")
    print(OUT, len(done), "cells")


if __name__ == "__main__":
    main()
