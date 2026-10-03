# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The verdict (omnicompass/verdict.py): Omni-Compass moves a knob only where it measures that the muscle is no worse.

  native     a muscle that is slower at every step down is left native: every trial refused, nothing allowed
  free       a muscle that costs nothing at the first steps: those steps are allowed, and the first step that costs more
             than the allowance is refused
  calm       a trial under stress is abandoned at once and the knob goes back
  recheck    a refused step is not tried again before its recheck time, and is tried again after it
  stepwise   incremental steps are held to the cost first measured at native, so they cannot add up past the allowance
  card       on the modelled card, compute-bound work: Omni on top of the firmware never makes a request more than the
             allowance slower than the firmware alone
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.verdict import Verdict


def drive(v, cost_at, decisions, calm=lambda t: True, per=40):
    step, log = 0, []
    for t in range(decisions):
        v.observe([cost_at(step)] * per)
        step, trial, ev = v.tick(calm(t))
        if ev:
            log.append(ev)
    return log


def main():
    # native: every step down is 1% slower; allowance 0.5%: nothing is ever allowed
    v = Verdict(tolerance=0.005, min_samples=30, probe_every=5, recheck=50)
    log = drive(v, lambda k: 10.0 * (1 + 0.01 * k), 400)
    assert v.allowed == 0 and v.state == "left native"
    assert any("refused" in e["verdict"] for e in log) and not any(e["verdict"] == "step allowed" for e in log)
    # free: the first three steps cost nothing, the fourth costs 5%
    v = Verdict(tolerance=0.02, min_samples=30, probe_every=3, recheck=10 ** 6)
    drive(v, lambda k: 10.0 if k <= 3 else 10.5, 200)
    assert v.allowed == 3 and v.state == "acting", v.allowed
    # calm: a trial that meets stress is abandoned
    v = Verdict(tolerance=0.02, min_samples=30, probe_every=1, recheck=10)
    log = drive(v, lambda k: 10.0, 6, calm=lambda t: t != 1, per=5)
    assert any("abandoned" in e["verdict"] for e in log)
    # recheck: a refused step waits its recheck time, then is tried again
    v = Verdict(tolerance=0.0, min_samples=10, probe_every=1, recheck=30)
    log = drive(v, lambda k: 10.0 + k, 100)
    tries = [i for i, e in enumerate(log) if e["verdict"] == "trial"]
    assert len(tries) >= 2 and v.allowed == 0
    # stepwise: each step 1.5% slower than the one before, allowance 2%: one step allowed, the second (3% past native)
    # refused although it is only 1.5% past the first
    v = Verdict(tolerance=0.02, min_samples=30, probe_every=3, recheck=10 ** 6, incremental=True)
    drive(v, lambda k: 10.0 * (1 + 0.015 * k), 200)
    assert v.allowed == 1, v.allowed
    # the card: compute-bound work, Omni on top of the firmware; no request more than the allowance slower at median
    from realms.gpu_card import run, ALLOW
    a, n = run(5000, "omni", duration=300.0), run(5000, "native", duration=300.0)
    assert a["p50_ms"] <= n["p50_ms"] * (1 + ALLOW) + 1e-9, (a["p50_ms"], n["p50_ms"])
    assert a["restored"] and a["served"] == n["served"]
    print("PASS verdict: left native where every step costs, free steps taken and the first costly one refused, trials "
          "abandoned under stress, refused steps rechecked, stepwise steps bounded by native, the card within its allowance")


if __name__ == "__main__":
    main()
