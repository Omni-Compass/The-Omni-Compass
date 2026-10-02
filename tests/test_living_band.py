# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The living band: every level the nervous system hands out stays within 5%..95% of its range, in every state.
N-band over 300,000 random engine states: cpufreq, GPU and power envelopes inside [0.05, 0.95]; routing (an amount moved)
never above 0.95. Conveyance over 20,000 random budgets and needs: every organ keeps at least 5% of its range (idle,
never off), never takes more than 95%, and the budget is never exceeded (energy is moved, not created)."""
import random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.nervous_system import NervousInputs, authority, BAND
from omnicompass.conveyance import Conveyance


def main():
    rng = random.Random(20260927); lo, hi = BAND; bad = 0
    for _ in range(300_000):
        i = NervousInputs(E=rng.uniform(-3, 3), U=rng.uniform(0, 1.5), I_U=rng.uniform(-1, 2), S=rng.uniform(0, 3),
                          push=rng.uniform(0, 2), security_block=rng.choice([0.0, 1.0]), slo_clean=rng.random() < 0.7,
                          power_stress=rng.uniform(0, 2), thermal=rng.uniform(0, 1.5), stale=rng.choice([0.0, 0.5]),
                          mode=rng.choice(["observe", "autopilot"]), killed=rng.random() < 0.05)
        org = authority(i)["organs"]
        for o in ("cpufreq", "gpu", "power"):
            if "envelope" in org.get(o, {}):            # killed / observe: no envelope is granted at all
                a, b = org[o]["envelope"]
                bad += not (lo - 1e-12 <= a <= b <= hi + 1e-12)
        if "envelope" in org.get("routing", {}):
            bad += org["routing"]["envelope"][1] > hi + 1e-12
    assert bad == 0, f"{bad} envelopes left the living band"
    worst = 0
    for _ in range(20_000):
        n = rng.randint(2, 8); cap = [rng.uniform(50, 1000) for _ in range(n)]
        budget = rng.uniform(0.1, 1.2) * sum(cap)
        c = Conveyance(n, budget)
        for _ in range(3):
            need = [rng.uniform(0, 1.2) * h for h in cap]
            a = c.step(need, [0.0] * n, cap)
            for x, h in zip(a, cap):
                worst += not (lo * h - 1e-6 <= x <= hi * h + 1e-6)
            assert sum(a) <= max(budget, sum(lo * h for h in cap)) + 1e-6, "budget exceeded"
    assert worst == 0, f"{worst} conveyance allocations left the living band"
    print("living band: 300,000 nervous states and 60,000 conveyance allocations, every level inside 5%..95%, budget kept")
    print("PASS test_living_band")


if __name__ == "__main__":
    main()
