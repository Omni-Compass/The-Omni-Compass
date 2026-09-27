"""Conveyance law: moving a conserved budget ("juice") between organs.

Manuscript sources (interpretation of the English, not only the symbols):
  Ch. 29 §8   E_system = E + U + S + B, dE_system/dt = 0 over the cycle: "Energy redistributes. Energy reorganizes.
              Energy does not diverge."                                   -> the budget is conserved, only moved
  Ch. 31 §4   "When E grows locally, B increases to distribute gradients." -> flow runs down the gradient of need
  Ch. 31 §5   stability requires Re(lambda_i) <= 0                          -> the flow must provably converge
  Ch. 30 §5-7 ignition is a "redistribution surge ... controlled release", with state continuity (no discontinuity)
                                                                            -> the reserve is released continuously
  Ch. 29 §6   compression: "backpressure develops through S ... structured inward rotation"
                                                                            -> surplus is pulled back smoothly

The law. Organs i hold allocations a_i of a budget A (watts, cores, ...), have need d_i (the budget that would serve
their work at the engine's utilisation target rho), and a deficit ("local deviation")
        e_i = d_i / (rho a_i) - 1        (> 0 needs juice, < 0 holds surplus)
The redistribution mediator moves budget by the replicator flow
        da_i/dt = kappa a_i (e_i - e_bar),       e_bar = sum_j a_j e_j / A
Properties (proved in docs/CONVEYANCE_LAW.md, checked in tests/test_conveyance.py):
  P1 conservation      sum_i da_i/dt = 0 exactly: the budget is moved, never created
  P2 gradient flow     it is the Shahshahani gradient of F(a) = sum_i (d_i / rho) ln a_i on the simplex sum a_i = A;
                       F is strictly concave, so F rises monotonically (Lyapunov function)
  P3 convergence       unique equilibrium a_i* = A d_i / D (D = sum d_i): every organ at the same deficit e*,
                       reached exponentially: da_i/dt = (kappa/rho)(d_i - a_i D/A), rate kappa D / (rho A), and the
                       linearisation has eigenvalues -kappa D/(rho A) < 0 (Re(lambda) <= 0, Ch. 31 §5)
  P4 bounds            organ floors and ceilings (device minimum, TDP) are kept by projection; budget an organ cannot
                       take because it is at its ceiling returns to the others (water-filling), and budget left over
                       when every organ is at its need is held back as reserve, not spent
Reserve (Ch. 30 surge): R = the budget needed to cover the demand rise the rate tracker projects over one actuation
delay; released continuously to organs whose deficit stays positive after the flow."""
from __future__ import annotations

from typing import List, Sequence


def deficits(a: Sequence[float], d: Sequence[float], rho: float) -> List[float]:
    return [di / (rho * max(ai, 1e-12)) - 1.0 for ai, di in zip(a, d)]


def replicator_step(a: Sequence[float], d: Sequence[float], rho: float, kappa: float, dt: float = 1.0) -> List[float]:
    """One exact step of da_i/dt = (kappa/rho)(d_i - a_i D/A), the closed form of the replicator flow (P3):
    a_i(t+dt) = a_i* + (a_i - a_i*) exp(-kappa D dt / (rho A)); conserves sum a_i to rounding (P1)."""
    import math
    A = sum(a); D = sum(d)
    if A <= 0 or D <= 0:
        return list(a)
    k = math.exp(-kappa * D * dt / (rho * A))
    return [A * di / D + (ai - A * di / D) * k for ai, di in zip(a, d)]


def project(a: Sequence[float], lo: Sequence[float], hi: Sequence[float], budget: float) -> List[float]:
    """Water-filling projection onto {lo_i <= a_i <= hi_i, sum a_i <= budget}: organs pinned at a bound keep it, the
    rest share the remainder in proportion to their unconstrained allocation (P4). Exact in <= n rounds."""
    a = [min(max(x, l), h) for x, l, h in zip(a, lo, hi)]
    for _ in range(len(a) + 1):
        tot = sum(a)
        if tot <= budget + 1e-9:
            return a
        free = [i for i in range(len(a)) if a[i] > lo[i] + 1e-12]
        over = tot - budget
        share = sum(a[i] - lo[i] for i in free)
        if share <= 0:
            return a
        a = [max(lo[i], a[i] - over * (a[i] - lo[i]) / share) if i in free else a[i] for i in range(len(a))]
    return a


class Conveyance:
    """The budget law for a set of organs sharing one budget (e.g. GPU groups under one site power cap).
    step(need, lo, hi) returns allocations; the flow moves budget toward need, the projection keeps bounds, and the
    reserve holds back what the projected rise needs, releasing it continuously where deficits stay positive."""

    def __init__(self, n: int, budget: float, rho: float = 0.8, kappa: float = 1.0):
        self.budget, self.rho, self.kappa = budget, rho, kappa
        self.a = [budget / n] * n
        self.prev = None
        self.rate = [0.0] * n

    def step(self, need: Sequence[float], lo: Sequence[float], hi: Sequence[float]) -> List[float]:
        # the living band: every organ keeps at least 5% of its range (idle, never off) and never takes more than 95%
        from omnicompass.nervous_system import BAND
        lo = [max(l, BAND[0] * h) for l, h in zip(lo, hi)]
        hi = [max(l, BAND[1] * h) for l, h in zip(lo, hi)]
        need = [max(x, 1e-9) for x in need]
        if self.prev is not None:           # rate tracker for the reserve (the dual-bath rate channel)
            self.rate = [0.5 * r + 0.5 * (x - p) for r, x, p in zip(self.rate, need, self.prev)]
        self.prev = list(need)
        reserve = min(0.5 * self.budget, sum(max(0.0, r) for r in self.rate))
        want = [min(h, x / self.rho) for x, h in zip(need, hi)]          # budget each organ can use at rho
        want = [max(w, l) for w, l in zip(want, lo)]                       # a device cannot go below its floor
        spend = max(sum(lo), min(self.budget - reserve, sum(want)))       # never spend budget nobody needs
        a = replicator_step(self.a, [w * self.rho for w in want], self.rho, self.kappa)
        a = [x * spend / max(sum(a), 1e-12) for x in a]
        a = project(a, lo, [max(l, min(h, w)) if sum(want) <= spend else h for l, h, w in zip(lo, hi, want)], spend)
        # surge (Ch. 30): release the reserve continuously to organs still in deficit, up to their ceiling
        left = self.budget - sum(a)
        short = [max(0.0, min(h, x / self.rho) - ai) for x, h, ai in zip(need, hi, a)]
        tot = sum(short)
        if tot > 0 and left > 0:
            a = [ai + min(s, left * s / tot) for ai, s in zip(a, short)]
        self.a = a
        return a
