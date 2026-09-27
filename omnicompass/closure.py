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
    z: float = 0.0             # deviation-bath band: a release must survive z standard deviations of the tracker's
                               # innovation over the release horizon (Chapter 31: the deviation bath carries the noise;
                               # the band is wide where demand is noisy, tight where it is calm)
    tone: bool = False         # muscle tone: release = park (alive, low power, instant wake), not power-off; parked
                               # machines beyond the reserve needed within tone_H are powered off
    site: bool = False         # whole body (multi-cluster sites): the law runs on the site total, one warm reserve for
                               # the site, and traffic shift lets a cluster use another's already-powered machines
    tone_H: int = 960          # reserve horizon (ticks): the largest demand seen over this window sets the warm reserve
    dwell: int = 0             # release only after this many consecutive calm decisions (resource-aware envelope,
                               # Proposition 2: no release outside the calm set; 0 = no dwell requirement)


class ClosureNodes:
    def __init__(self, law: ClosureLaw = ClosureLaw()):
        self.L = None; self.v = 0.0; self.law = law; self.calm = 0; self.s2 = 0.0; self.hist = []

    def observe(self, r: float, dt: float = 1.0) -> None:
        a, b, g = self.law.a, self.law.b, self.law.g
        if self.law.tone:
            self.hist.append(r)
            if len(self.hist) > self.law.tone_H:
                self.hist.pop(0)
        if self.L is None:
            self.L = r; return
        pred = self.L + self.v * dt
        e = r - pred
        self.s2 = 0.95 * self.s2 + 0.05 * e * e
        self.L = pred + a * e
        self.v = (1.0 - g) * self.v + b * e / dt

    def reserve(self, c: float) -> int:
        """Machines the law expects to need within the tone horizon (largest recent demand at the working boundary)."""
        if not self.hist:
            return 0
        return int(math.ceil(max(self.hist) / ((self.law.rho_max - self.law.delta) * c) - 1e-9))

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
        peak_rel = max(self.fwd_max(L.H_rel), 0.0) + L.z * math.sqrt(self.s2 * max(1, L.H_rel)) * L.a
        band = L.delta if L.delta_rel < 0 else L.delta_rel
        calm = n - 1 >= n_min and peak_rel / ((n - 1) * c) <= L.rho_max - band \
            and (not L.turn or self.v <= 0.0) and push <= L.push_release
        self.calm = self.calm + 1 if calm else 0
        if calm and self.calm > L.dwell:
            self.calm = 0
            return n - 1
        return n


# ---------------------------------------------------------------------------------------------------------------------
# Self-calibrating closure law: every margin is derived, none is tuned per workload.
#
#   tracker      dual bath with the critically damped alpha-beta relation (Benedict-Bordner): b = a^2 / (2 - a), a = 1/2
#   noise        sigma^2 = running variance of the tracker's one-step innovation (the deviation bath of Chapter 31)
#   add horizon  H_add = boot delay + 1 tick: a machine ordered now is serving when the projection arrives
#   release hor. H_rel = boot delay / park fraction: the energy break-even between keeping a machine parked and booting
#                it cold again (a parked machine draws park_frac x idle per tick, a cold start draws boot x idle)
#   boundary     requested cores <= allocatable cores (rho_max = 1, the physical limit); no fixed margin
#   margin       z(t) sigma sqrt(H): the forecast error over the horizon at confidence z;
#                z(t) = z95 x max(1, S / S*), S the six-state engine's stress (equation 6) and S* its equilibrium,
#                delta - alpha_s S* - (3/4) beta_s S*^2 = 0: the engine widens the margin when it is stressed
#   Gc (add)     if projected peak over H_add + margin > n c: add ceil((peak + margin) / c) - n machines
#   G0 (release) one machine, only if projected peak over H_rel + margin <= (n - 1) c, after the turn (v <= 0), and while
#                the engine's push <= push_release; the released machine is parked; parked machines beyond what the
#                projection over H_rel needs are powered off
# ---------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class AutoClosureLaw:
    boot: int = 6                  # boot delay of a cold machine (ticks): a property of the plant
    park_frac: float = 0.25        # parked power / idle power: a property of the hardware
    z95: float = 1.6449            # one-sided 95% normal quantile
    a: float = 0.5
    push_release: float = 0.2
    site: bool = False
    # read by the plant (same interface as ClosureLaw)
    tone: bool = True
    rho_max: float = 1.0
    delta: float = 0.0

    @property
    def b(self) -> float:
        return self.a * self.a / (2.0 - self.a)

    @property
    def H_add(self) -> int:
        return self.boot + 1

    @property
    def H_rel(self) -> int:
        return int(math.ceil(self.boot / self.park_frac))

    @property
    def tone_H(self) -> int:
        return self.H_rel


def stress_equilibrium(delta: float, alpha_s: float, beta_s: float) -> float:
    """Positive root of delta - alpha_s S - (3/4) beta_s S^2 = 0 (the engine's stress equilibrium, equation 6)."""
    qa = 0.75 * beta_s
    return (-alpha_s + math.sqrt(alpha_s * alpha_s + 4.0 * qa * delta)) / (2.0 * qa) if qa > 0 else delta / alpha_s


class AutoClosureNodes:
    def __init__(self, law: AutoClosureLaw = AutoClosureLaw(), s_eq: float = None):
        self.law = law; self.L = None; self.v = 0.0; self.s2 = 0.0; self.n_obs = 0
        self.S = 0.0; self.s_eq = s_eq if s_eq else stress_equilibrium(0.5, 0.12, 0.10)
        self.hist = []

    def observe(self, r: float, dt: float = 1.0) -> None:
        a, b = self.law.a, self.law.b
        if self.L is None:
            self.L = r; return
        pred = self.L + self.v * dt
        e = r - pred
        self.n_obs += 1
        w = max(1.0 / self.n_obs, 0.02)            # running mean first, then a 50-tick exponential window
        self.s2 = (1.0 - w) * self.s2 + w * e * e
        self.L = pred + a * e
        self.v = self.v + b * e / dt

    def z(self) -> float:
        return self.law.z95 * max(1.0, self.S / self.s_eq) if self.s_eq > 0 else self.law.z95

    def peak(self, H: int) -> float:
        if self.L is None:
            return 0.0
        return max(self.L + self.v * tau for tau in range(0, H + 1)) + self.z() * math.sqrt(self.s2 * H)

    def reserve(self, c: float) -> int:
        return int(math.ceil(max(self.peak(self.law.H_rel), 0.0) / c - 1e-9))

    def decide(self, n: int, c: float, push: float, n_min: int, n_max: int) -> int:
        L = self.law
        if self.L is None:
            return n
        need = int(math.ceil(max(self.peak(L.H_add), 0.0) / c - 1e-9))
        if n <= 0 or need > n:
            return int(min(n_max, max(n_min, need)))
        if n - 1 >= n_min and self.peak(L.H_rel) <= (n - 1) * c and self.v <= 0.0 and push <= L.push_release:
            return n - 1
        return n
