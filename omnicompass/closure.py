"""Closure governor: machines governed by the Omni-Compass closure law, preemptive coherence and the dual-bath tracker.

Sources (the owner's manuscript): Section 5 (5c preemptive coherence: forward projection tau_fwd = Phi_dt(x) and
correction -lambda grad psi), Chapter 20 (master closure law F = G0 + Gc, Gc = -rho beta Dh, zero in the interior,
inward near the boundary with margin delta), Chapters 29-30 (the wheel: expansion, turning point dE/dt = 0, compression;
release only after the turn, ignition before the threshold), Chapter 31 (dual-bath exchange dU/dt = -alpha E + beta S,
dE/dt = alpha U - gamma B).

Cluster realisation (one pool)
  state        r(t)  requested cores (what the pods ask for);  n machines;  c = cores x ALLOC per machine
  dual bath    level L and rate v of r, the exchange pair of Chapter 31 in discrete form:
                 innovation e = r - (L + v dt)
                 L <- L + v dt + a e          (coherence bath absorbs the observation)
                 v <- (1 - g) v + b e / dt    (deviation bath exchanges with it; g = redistribution damping)
  projection   r_fwd(tau) = L + v tau  for tau in [0, H]          (5c: Phi over the look-ahead horizon)
  admissible   h(tau) = r_fwd(tau) / (n c) - rho_max  <= 0      (Chapter 20: the admissible domain)
  closure Gc   if max_{tau <= H_add} h(tau) > -delta (projected boundary approach, within one boot of lead):
                 add k = ceil( (max r_fwd / (rho_max - delta) - n c) / c ) machines        (beta sized to restore delta)
  interior G0  energy descent: remove one machine only if it stays admissible with margin for the whole release horizon,
                 max_{tau <= H_rel} r_fwd(tau) / ((n - 1) c) <= rho_max - delta,
               and only after the turn (v <= 0: past the peak, the metric flip), and only while the six-state engine's
               equation (2) push <= push_release
  interior     nothing else happens: inside the domain the platform physics runs unmodified (Gc = 0)
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ClosureLaw:
    rho_max: float = 0.95      # admissibility boundary: requested cores / allocatable cores
    delta: float = 0.05        # inwardness margin
    H_add: int = 8             # look-ahead for the closure correction (ticks); >= the boot delay
    H_rel: int = 40            # look-ahead a release must survive (ticks)
    a: float = 0.5             # dual-bath coupling: level absorption
    b: float = 0.1             # dual-bath coupling: rate exchange
    g: float = 0.05            # redistribution damping of the rate bath
    push_release: float = 0.2  # engine gate on release
    turn: bool = True          # release only after the turning point (v <= 0)
    delta_rel: float = -1.0    # release band: a release must fit at rho_max - delta_rel (hysteresis; < 0 means = delta)
    dwell: int = 0             # release only after this many consecutive calm decisions (resource-aware envelope,
                               # Proposition 2: no release outside the calm set; 0 = no dwell requirement)


class ClosureNodes:
    def __init__(self, law: ClosureLaw = ClosureLaw()):
        self.L = None; self.v = 0.0; self.law = law; self.calm = 0

    def observe(self, r: float, dt: float = 1.0) -> None:
        a, b, g = self.law.a, self.law.b, self.law.g
        if self.L is None:
            self.L = r; return
        pred = self.L + self.v * dt
        e = r - pred
        self.L = pred + a * e
        self.v = (1.0 - g) * self.v + b * e / dt

    def fwd_max(self, H: int) -> float:
        return max(self.L + self.v * tau for tau in range(0, H + 1)) if self.L is not None else 0.0

    def decide(self, n: int, c: float, push: float, n_min: int, n_max: int) -> int:
        """Target machine count for this tick."""
        L = self.law
        if self.L is None:
            return n
        peak_add = max(self.fwd_max(L.H_add), 0.0)
        if n <= 0 or peak_add / (n * c) - L.rho_max > -L.delta:
            self.calm = 0
            need = math.ceil(peak_add / ((L.rho_max - L.delta) * c) - 1e-9)
            return int(min(n_max, max(n_min, need, n)))
        peak_rel = max(self.fwd_max(L.H_rel), 0.0)
        band = L.delta if L.delta_rel < 0 else L.delta_rel
        calm = n - 1 >= n_min and peak_rel / ((n - 1) * c) <= L.rho_max - band \
            and (not L.turn or self.v <= 0.0) and push <= L.push_release
        self.calm = self.calm + 1 if calm else 0
        if calm and self.calm > L.dwell:
            self.calm = 0
            return n - 1
        return n
