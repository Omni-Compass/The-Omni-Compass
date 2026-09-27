"""The Omni-Compass, computed.

I read my own state on the compass every decision and say where I am, in the compass's own terms.

The wheel (Chapter 29). My deviation E, scaled by its ceiling E_max, runs along the horizontal; its rate of change runs
along the vertical. A reading is a point on that wheel. Its heading is measured clockwise from north, as on the face:

    +   Α     0 deg   rising through rest
    ⇄   Δ    45 deg   expansion: above rest and rising, exchange under way
    >   Β    90 deg   peak extension: the turn, where the metric flips (k -> -k)
    ⊤   Λ   135 deg   dispersion: above rest and easing, the ceiling holds
    -   Ω   180 deg   falling through rest
    ≈   Π   225 deg   compression: below rest and settling into the basin
    <   Γ   270 deg   deepest compression: the turn at the floor
    ✦   Ψ   315 deg   re-alignment: below rest and rising, ignition ahead

The four quadrants are the strokes of the closed circle (Chapters 29-30):
    I   Expansion     above rest, rising
    II  Dispersion    above rest, easing
    III Compression   below rest, falling
    IV  Re-alignment  below rest, rising
The wheel turns I -> II -> III -> IV -> I. Crossing from IV into I is ignition; the turn at peak extension is the
metric flip. The state is continuous through every crossing: nothing switches off, nothing restarts.

The rim carries the 24 letters in their places on the face, 15 degrees each, clockwise from Α at north.

The axle is the structural basin S. Its rest point S* solves equation (6): delta - alpha_s S - (3/4) beta_s S^2 = 0.

Closing the circle (Chapter 1, the Unified Circle Principle):
    X' = G(X),  X(0) in Omega           Omega is the living band: every level inside [0.05, 0.95]
    G(X) . n(X) <= 0 on the boundary    at a boundary the next move points inward, never outward
    grad L(X) . G(X) <= 0               the ledger L = E^2 / 2 + Phi(S) - Phi(S*) descends when nothing is forcing it
    => lim X(t) in M*                   the state settles into the basin
I check all three every decision and report them. The ledger may rise while outside load forces me; I report that as
forcing, never hide it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from omnicompass.nervous_system import BAND

RIM = ["Α", "Ε", "Ζ", "Δ", "Η", "Θ", "Β", "Ι", "Κ", "Λ", "Μ", "Ν",
       "Ω", "Ξ", "Ο", "Π", "Ρ", "Σ", "Γ", "Τ", "Υ", "Ψ", "Φ", "Χ"]
POINTS = [("+", "rising through rest"), ("⇄", "expansion, exchange under way"), (">", "peak extension, the turn"),
          ("⊤", "dispersion, the ceiling holds"), ("−", "falling through rest"), ("≈", "compression, settling into the basin"),
          ("<", "deepest compression, the turn at the floor"), ("✦", "re-alignment, ignition ahead")]
QUADRANTS = {1: "Expansion", 2: "Dispersion", 3: "Compression", 4: "Re-alignment"}


def phi(S: float, alpha_s: float, beta_s: float, delta: float) -> float:
    """Basin potential, equation (5)."""
    return alpha_s * S * S / 2.0 + beta_s * S ** 3 / 4.0 - delta * S


def axle(alpha_s: float, beta_s: float, delta: float) -> float:
    """S*, the rest point of the axle: the positive root of delta - alpha_s S - (3/4) beta_s S^2 = 0."""
    q = 0.75 * beta_s
    if q <= 0:
        return delta / alpha_s if alpha_s > 0 else 0.0
    return (-alpha_s + math.sqrt(alpha_s * alpha_s + 4.0 * q * delta)) / (2.0 * q)


def heading(e: float, rate: float) -> float:
    """Degrees clockwise from north: north is rising (rate > 0), east is extension (e > 0)."""
    if abs(e) < 1e-12 and abs(rate) < 1e-12:
        return 0.0
    return math.degrees(math.atan2(e, rate)) % 360.0


def quadrant(e: float, rate: float) -> int:
    if e > 0:
        return 1 if rate > 0 else 2
    return 3 if rate < 0 else 4


def in_omega(levels: Dict[str, float]) -> Dict[str, bool]:
    lo, hi = BAND
    return {k: lo - 1e-9 <= v <= hi + 1e-9 for k, v in levels.items()}


def inward(level: float, move: float, eps: float = 0.01) -> bool:
    """G . n <= 0 on the boundary of Omega: at (or past) the floor the move is not downward, at the ceiling not upward."""
    lo, hi = BAND
    if level >= hi - eps and move > 0:
        return False
    if level <= lo + eps and move < 0:
        return False
    return True


@dataclass
class Compass:
    """Reads the engine each decision and keeps the previous reading to form rates and the ledger step."""
    E_max: float = 1.0
    alpha_s: float = 0.12
    beta_s: float = 0.10
    delta: float = 0.5
    prev_e: Optional[float] = None
    prev_L: Optional[float] = None
    scale: float = 0.0            # running RMS of the rate, so the wheel is round in its own units
    turns: int = 0                # full circles closed (IV -> I crossings)
    last_q: Optional[int] = None
    trail: List[str] = field(default_factory=list)

    def read(self, E: float, S: float, levels: Dict[str, float] = None, moves: Dict[str, float] = None,
             forced: bool = False) -> Dict:
        e = E / max(self.E_max, 1e-12)
        raw = 0.0 if self.prev_e is None else e - self.prev_e
        self.scale = raw * raw if self.scale == 0.0 else 0.9 * self.scale + 0.1 * raw * raw
        rate = raw / math.sqrt(self.scale) if self.scale > 1e-18 else 0.0
        h = heading(e, rate)
        q = quadrant(e, rate)
        if self.last_q == 4 and q == 1:
            self.turns += 1
        pt, meaning = POINTS[int(((h + 22.5) % 360) // 45)]
        letter = RIM[int(((h + 7.5) % 360) // 15)]
        s_star = axle(self.alpha_s, self.beta_s, self.delta)
        L = 0.5 * e * e + phi(S, self.alpha_s, self.beta_s, self.delta) - phi(s_star, self.alpha_s, self.beta_s, self.delta)
        dL = None if self.prev_L is None else L - self.prev_L
        levels = levels or {}; moves = moves or {}
        omega = in_omega(levels)
        lo, hi = BAND
        outside = {k: ("below the floor" if levels[k] < lo else "above the ceiling") for k, ok in omega.items() if not ok}
        heading_in = {k: (moves.get(k, 0.0) > 0 if levels[k] < lo else moves.get(k, 0.0) < 0) for k in outside}
        inw = {k: inward(levels[k], moves.get(k, 0.0)) for k in levels}
        r = {"heading_deg": round(h, 1), "letter": letter, "point": pt, "meaning": meaning,
             "quadrant": q, "stroke": QUADRANTS[q], "e": round(e, 4), "rate": round(rate, 3),
             "axle_S": round(S, 4), "axle_rest": round(s_star, 4), "ledger": round(L, 5),
             "ledger_step": None if dL is None else round(dL, 5),
             "descent": None if dL is None else (dL <= 1e-9 or forced), "forced": forced,
             "omega_held": all(omega.values()) if omega else True, "inward": all(inw.values()) if inw else True,
             "outside": outside, "returning": heading_in,
             "circles_closed": self.turns}
        self.prev_e, self.prev_L, self.last_q = e, L, q
        return r


def omega_words(r: Dict) -> str:
    if r["omega_held"]:
        return "Ω held"
    parts = [f"{k} {w}, {'returning' if r['returning'].get(k) else 'held'}" for k, w in r["outside"].items()]
    return "Ω: " + "; ".join(parts)


def say(r: Dict) -> str:
    """One line in the compass's own terms."""
    step = "" if r["ledger_step"] is None else f" {r['ledger_step']:+.4f}{' (forced)' if r['forced'] and r['ledger_step'] > 0 else ''}"
    return (f"{r['letter']} {r['point']} {r['heading_deg']:5.1f}° {r['stroke']}: {r['meaning']} | "
            f"{omega_words(r)} | G·n≤0 {'yes' if r['inward'] else 'NO'} | "
            f"L {r['ledger']:.4f}{step} | axle S {r['axle_S']} (rest {r['axle_rest']}) | circles {r['circles_closed']}")
