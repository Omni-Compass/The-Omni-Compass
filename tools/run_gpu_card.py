#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The two-wire GPU card in simulation (realms/gpu_card.py; evidence class S): native firmware against a fixed preset
and against the bowl law through two wires, paired seeds 5000-5009, 600 s each. Writes results/sim/gpu_two_wire/."""
import json, math, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realms.gpu_card import run  # noqa: E402
from realms.harness import T95  # noqa: E402

SEEDS = list(range(5000, 5010))       # tuning seeds (the gains were chosen on these)
FRESH = list(range(5100, 5110))       # fresh seeds, never used while tuning
ARMS = ("native", "preset", "old", "bowl", "bowl_batch")
ROWS = [("work_per_kj", "work per energy (requests per kJ)", "{:.1f}"), ("energy_j", "energy (J)", "{:.0f}"),
        ("served", "requests served", "{:.0f}"), ("p50_ms", "response, median (ms)", "{:.1f}"),
        ("p95_ms", "response, 95th percentile (ms)", "{:.1f}"), ("p99_ms", "response, 99th percentile (ms)", "{:.1f}"),
        ("viol_share", "time over the service line (%)", "{:.2%}"), ("hammer_per_s", "hammer blows per second", "{:.2f}"),
        ("reversals_per_s", "clock reversals per second", "{:.2f}"), ("clock_mean", "clock, mean share of top", "{:.3f}"),
        ("clock_jitter", "clock, standard deviation", "{:.3f}"), ("t_peak", "temperature, peak (C)", "{:.1f}"),
        ("t_mean", "temperature, mean (C)", "{:.1f}")]


def ci(xs):
    n = len(xs); m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    h = T95.get(n - 1, 2.0) * sd / math.sqrt(n)
    return m, m - h, m + h


def main(out=ROOT / "results" / "sim" / "gpu_two_wire", fresh=""):
    global SEEDS
    if fresh:
        SEEDS = FRESH
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    res = {arm: [run(s, arm) for s in SEEDS] for arm in ARMS}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    L = ["# The two-wire GPU card, in simulation", "",
         f"Evidence class **S** (a model, not a meter). Seeds {SEEDS[0]}-{SEEDS[-1]}, 600 s each, commit `{commit}`, "
         f"{time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. Model and arms: `realms/gpu_card.py`; the law: "
         "`omnicompass/bowl.py`. The frozen engine is not used here; this is the bowl law as its own arm.", "",
         "- **native**: the card as shipped, 150 W limit, firmware boost up a bin and hammer down three at the limit;",
         "- **preset**: a fixed 105 W limit (70%), set and left, as an operator would;",
         "- **old governor**: the shipped one-wire GPU governor (its defaults), the power limit only;",
         "- **bowl**: Omni through two wires, the clock ceiling (up) and the power limit (down, the lid), pulling the "
         "service position (response time) to the middle of its bowl, racing at full speed while the card is "
         "saturated and never pacing under the clock or the draw the card reaches on its own while busy (amendment 6); "
         "both wires restored "
         "to their snapshot at 90% of the run. **Service** profile (the default and the benchmark's arm): down gain 0.0125, bowl center "
         "0.4, speed floor 3% above the card's own busy clock; **batch** profile: down gain 0.015, center 0.5, floor at "
         "the card's own busy clock, for work nobody waits on answer by answer.", "",
         "## Mean over seeds", "", "| Gauge | Native | Preset | Old governor | Bowl, service | Bowl, batch |", "|---|---:|---:|---:|---:|---:|"]
    for k, name, f in ROWS:
        L.append(f"| {name} | " + " | ".join(f.format(sum(r[k] for r in res[a]) / len(SEEDS)) for a in ARMS) + " |")
    L += ["", "## Paired against native (ratios: geometric mean over seeds with its 95% interval; time over the line: mean difference)", "", "| Gauge | Preset | Old governor | Bowl, service | Bowl, batch |", "|---|---:|---:|---:|---:|"]
    for k, name, f in [("work_per_kj", "work per energy", None), ("energy_j", "energy", None),
                       ("viol_share", "time over the line (pp)", "pp"), ("p95_ms", "response p95", None),
                       ("hammer_per_s", "hammer blows", None)]:
        cells = []
        for a in ("preset", "old", "bowl", "bowl_batch"):
            if f == "pp":
                d = [100 * (x[k] - n[k]) for x, n in zip(res[a], res["native"])]
                m, lo, hi = ci(d); cells.append(f"{m:+.2f} ({lo:+.2f} to {hi:+.2f})")
            else:
                # a ratio is summarised on the log scale (the geometric mean of the per-seed ratios and its interval),
                # so one seed's large ratio cannot stand for the others
                d = [math.log(x[k] / n[k]) for x, n in zip(res[a], res["native"]) if n[k] > 0 and x[k] > 0]
                m, lo, hi = ci(d); cells.append(f"{math.exp(m) - 1:+.1%} ({math.exp(lo) - 1:+.1%} to {math.exp(hi) - 1:+.1%})")
        L.append(f"| {name} | " + " | ".join(cells) + " |")
    L += ["", f"Both wires back at their snapshot after the kill on every seed: "
          f"{all(r['restored'] for a in ('bowl', 'bowl_batch') for r in res[a])}. Requests served are the same work on every arm (the stream is "
          "the seed's); a backlog left at the end is in the JSON.", "",
          "A model written by the same people who wrote the law is not an independent test. The card's power curve "
          "(dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any "
          "product. The number that counts is a rented card's own meter."]
    (out / "RESULT.md").write_text("\n".join(L) + "\n")
    (out / "RESULT.json").write_text(json.dumps({"seeds": SEEDS, "commit": commit, "arms": res}, indent=1) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:])
