"""The bowl: one smooth law for every muscle, and the plug every muscle is wired through.

A muscle is a plug with one wire in and one wire out. The plug reads its meters and writes its lever; all the
thinking is here, in the brain, written once for every muscle.

The plug (Plug)
  read      the service reading (response time, temperature, queue) and the lever as it stands
  write     one value; the plug clips it to the cover, sends it, and reads back what the device took
  restore   the lever back to the snapshot, the value read once before the first write; it never moves after that
  one writer if the lever is found at a value the brain did not write, someone else owns it: the brain stops writing
            and leaves that value alone (restoring over it would fight the new owner)

Two bands
  cover     the outer band, the lever's hard range (the device's or the buyer's lowest and highest setting); every
            write is clipped to it, so nothing the math does can set the lever outside
  bowl      the service reading as a position in its band, 0 to 1 (0: calm, 1: the service line); the brain pulls it
            to the bottom of the bowl, the center (0.5 by default); the walls run to 0.05 and 0.95, and the last 5% on
            each side is cushion (10% in all) before the line

The force (Bowl.force), the physics of a ball in a bowl with the right friction
  pull      K_P x (position - center): gentle near the bottom, harder up the walls
  push      K_D x velocity: whatever is shoving the position (a load rising, heat building) is met by an equal and
            opposite push; it is also the friction that stops the ball sloshing past the bottom (with K_D chosen for
            critical damping it glides to the center and stops, no overshoot, no ringing)
  smooth    the force is A x tanh(raw / A): a spring near the center that bends over and flattens into its maximum A,
            never a corner, never a hammer; the same shape the engine already uses for v_eff (omnicompass/core.py)
  fail up   past the 0.95 wall the up side goes to its full force at once, and the down side may not act until the
            position is back inside the bowl

  walls     with kw > 0, each edge of the band repels like a charge of the same sign: a force growing as 1/distance^2
            near the wall, nothing at the center (the two walls cancel there). It is the slope of the walls' potential,
            so the field itself points inward at the boundary (G(X).n(X) <= 0 on the boundary: nothing crosses) and the
            bowl's energy only falls (grad L . G <= 0): the Unified Circle Principle, written as the force

Two forces (antagonist pairs)
  up        a positive force adds capacity, power, cooling or speed (scale out, raise a clock, start a chiller)
  down      a negative force takes it back (scale in, lower a limit, warm a setpoint)
  each side has its own gain (lever units per unit of force), because adding and taking back do not cost the same;
  a muscle with two wires (a GPU's clock range and power limit) gives each side its own lever; a one-wire muscle
  carries both directions on its one lever

The frozen engine (omnicompass/core.py) and its proofs are untouched; this is a separate law, run as its own arm.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


@dataclass
class Band:
    """A reading's band: lo is calm (position 0), hi is the line (position 1)."""
    lo: float
    hi: float
    center: float = 0.5
    cushion: float = 0.05

    def position(self, x: float) -> float:
        return (x - self.lo) / (self.hi - self.lo)

    @property
    def wall_low(self) -> float:
        return self.cushion

    @property
    def wall_high(self) -> float:
        return 1.0 - self.cushion


@dataclass
class Bowl:
    """The brain's law for one muscle. dt: seconds between decisions; tau: the muscle's response time in seconds
    (how long the service reading takes to follow the lever); kd defaults to critical damping for that response."""
    band: Band
    dt: float
    tau: float
    kp: float = 1.0
    kd: Optional[float] = None
    authority: float = 1.0
    kw: float = 0.0              # the walls' repulsion (like charges at 0 and 1): kw x (1/(1-p)^2 - 1/p^2)
    smooth: float = 0.5          # the velocity estimate's smoothing (0: raw difference, near 1: heavily smoothed)
    p: Optional[float] = field(default=None, init=False)
    v: float = field(default=0.0, init=False)

    def __post_init__(self):
        if self.kd is None:
            # a first-order muscle with response tau under a P-D pull: critical damping when kd = 2 sqrt(kp tau) - 1
            # scaled to the decision period; never negative
            self.kd = max(0.0, 2.0 * math.sqrt(self.kp * self.tau / self.dt) - 1.0) * self.dt

    def sense(self, reading: float) -> float:
        p = self.band.position(reading)
        if self.p is not None:
            self.v = self.smooth * self.v + (1.0 - self.smooth) * (p - self.p) / self.dt
        self.p = p
        return p

    def force(self, reading: float) -> float:
        """Positive: the up side (add capacity); negative: the down side (take it back). Bounded by the authority."""
        p = self.sense(reading)
        if p >= self.band.wall_high:
            return self.authority                                  # fail up: past the wall, full force up at once
        q = clamp(p, 1e-3, 1.0 - 1e-3)
        raw = self.kp * (p - self.band.center) + self.kd * self.v + self.kw * (1.0 / (1.0 - q) ** 2 - 1.0 / q ** 2)
        f = self.authority * math.tanh(raw / self.authority)
        if f < 0.0 and self.v > 0.0 and p > self.band.center:
            f = 0.0                                                # never take back while it climbs above the center
        return f


class ForeignWriter(Exception):
    pass


class Plug:
    """One wire in, one wire out. Subclasses implement _read_service, _read_lever and _send; everything else is here."""

    def __init__(self, lo: float, hi: float, tolerance: float = 1e-6):
        self.lo, self.hi, self.tol = lo, hi, tolerance
        self.snapshot: Optional[float] = None
        self.last_written: Optional[float] = None
        self.owned = True
        self.writes = 0
        self.clipped = 0

    # the wires ----------------------------------------------------------------------------------------------------
    def _read_service(self) -> float:
        raise NotImplementedError

    def _read_lever(self) -> float:
        raise NotImplementedError

    def _send(self, value: float) -> None:
        raise NotImplementedError

    # the contract -------------------------------------------------------------------------------------------------
    def attach(self) -> float:
        """Read the lever once, before any write: the restore point. It never moves after this."""
        self.snapshot = self._read_lever()
        return self.snapshot

    def read(self) -> float:
        return self._read_service()

    def lever(self) -> float:
        return self._read_lever()

    def write(self, value: float) -> Optional[float]:
        """Clip to the cover, check nobody else moved the lever, send, read back. None: not written (not owned)."""
        if not self.owned:
            return None
        now = self._read_lever()
        expected = self.last_written if self.last_written is not None else self.snapshot
        if expected is not None and abs(now - expected) > self.tol:
            self.owned = False                                     # someone else moved it: it is theirs now
            raise ForeignWriter(f"lever at {now}, last written {expected}")
        v = clamp(value, self.lo, self.hi)
        self.clipped += int(v != value)
        if abs(v - now) <= self.tol:
            return now
        self._send(v)
        self.last_written = self._read_lever()
        self.writes += 1
        return self.last_written

    def restore(self) -> bool:
        """The lever back to the snapshot. Left alone when someone else owns it. True: at the snapshot (or not ours)."""
        if not self.owned or self.snapshot is None:
            return True
        if abs(self._read_lever() - self.snapshot) > self.tol:
            self._send(self.snapshot)
        self.last_written = None
        return abs(self._read_lever() - self.snapshot) <= self.tol
