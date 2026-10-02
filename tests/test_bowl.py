# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The bowl law and the plug (omnicompass/bowl.py), and the two-wire card model (realms/gpu_card.py)."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omnicompass.bowl import Band, Bowl, Plug, ForeignWriter  # noqa: E402
from realms.gpu_card import run  # noqa: E402


class Lever(Plug):
    def __init__(self, lo, hi, start):
        super().__init__(lo, hi)
        self.v, self.svc = start, 0.5

    def _read_service(self):
        return self.svc

    def _read_lever(self):
        return self.v

    def _send(self, v):
        self.v = v


def main():
    # the band: position, walls, cushions
    b = Band(lo=10.0, hi=110.0)
    assert b.position(60.0) == 0.5 and b.wall_low == 0.05 and abs(b.wall_high - 0.95) < 1e-12

    # the force is smooth and bounded: never past the authority, no corner, zero at the center, signed by side
    w = Bowl(Band(0.0, 1.0), dt=1.0, tau=2.0, authority=1.0)
    assert w.force(0.5) == 0.0
    w = Bowl(Band(0.0, 1.0), dt=1.0, tau=2.0, authority=1.0)
    assert w.force(0.9) > 0.0                                  # above the center: the up side
    w = Bowl(Band(0.0, 1.0), dt=1.0, tau=2.0, authority=1.0)
    assert w.force(0.1) < 0.0                                  # below: the down side
    xs = [i / 200 for i in range(int(0.94 * 200))]
    fs = []
    for x in xs:
        w = Bowl(Band(0.0, 1.0), dt=1.0, tau=2.0, kp=4.0, authority=1.0)
        fs.append(w.force(x))
    assert all(abs(f) < 1.0 for f in fs)                        # tanh: it flattens toward the authority, never hits it
    assert all(b2 >= a for a, b2 in zip(fs, fs[1:]))            # monotone: harder the farther out
    w = Bowl(Band(0.0, 1.0), dt=1.0, tau=2.0, authority=1.0)
    assert w.force(0.97) == 1.0                                 # past the wall: full force up at once (fail up)

    # a first-order muscle under the bowl settles at the center with no overshoot (critical damping or more)
    w = Bowl(Band(0.0, 1.0), dt=0.1, tau=2.0, kp=1.0)
    x, lever, hist = 0.9, 0.0, []
    for _ in range(2000):
        F = w.force(x)
        lever += 0.1 * F * w.dt                                 # more capacity lowers the reading
        x += (0.9 - lever - x) * w.dt / 2.0
        hist.append(x)
    assert abs(hist[-1] - 0.5) < 0.01 and min(hist) > 0.5 - 0.01

    # the plug: the cover clips, the restore point is taken once and never moves, a foreign writer ends the writing
    p = Lever(105.0, 150.0, 150.0)
    assert p.attach() == 150.0
    for v in (140, 132, 90, 200, 138):
        p.write(v)
        assert 105.0 <= p.v <= 150.0
    assert p.clipped == 2 and p.snapshot == 150.0
    assert p.restore() and p.v == 150.0                         # back to the snapshot, not to the last write
    p = Lever(105.0, 150.0, 150.0); p.attach(); p.write(130.0)
    p.v = 120.0                                                 # someone else moves it
    try:
        p.write(125.0); raise AssertionError("a foreign write was not caught")
    except ForeignWriter:
        pass
    assert p.write(125.0) is None and p.restore() and p.v == 120.0   # theirs now: left alone, not restored over

    # the card: deterministic, both wires restored, and the bowl writes nothing on the native arm
    a, c = run(5000, "bowl", duration=120.0), run(5000, "bowl", duration=120.0)
    assert a == c and a["restored"] and a["writes"] > 0
    assert run(5000, "native", duration=120.0)["writes"] == 0
    print("PASS test_bowl: band and cushions, smooth bounded signed force, fail up, settles at the center without "
          "overshoot, cover clips, one restore point, foreign writer left alone, two-wire card restored and deterministic")


if __name__ == "__main__":
    main()
