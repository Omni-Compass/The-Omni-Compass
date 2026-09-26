"""Omni-Compass core: six-state ODE, RK4 integrator, bounded feedforward-plus-proportional controller.

State x = (E, U, I_U, S, B, B_dot).

  (1) dE/dt    = -alpha_E E + beta_int + beta_ext + v_eff
  (2) dU/dt    = mu U (1 - U^2) - (dE/dt)/E_max - lambda_U U + u,   |u| <= U_AUTHORITY
  (3) dI_U/dt  = (1 - U) - sigma_1 E - delta S - lambda_I I_U
  (4) v_eff    = cos(omega_B t / 2) * c * tanh(lambda_0 + lambda_1 (U - 0.5) + lambda_2 S)
  (5) Phi(S)   = alpha_s S^2 / 2 + beta_s S^3 / 4 - delta S
  (6) dS/dt    = -dPhi/dS = delta - alpha_s S - (3/4) beta_s S^2
  (7) dB/dt    = B_dot ;  dB_dot/dt = gamma_c delta S - (omega_B/Q_B) B_dot - omega_B^2 B
  (8) R_B[n]   = finite-difference audit of (7); never fed back into the state.

Controller (one micro step, zero-order hold across all four RK4 stages):
  u = clip(-f_U(x, t) + KP (sigma - U), -U_AUTHORITY, +U_AUTHORITY)
where f_U is the uncontrolled U drift and sigma in {-1, +1} is the locked target.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict, fields
from typing import Dict, List, Optional, Tuple

EPS = 1e-12
KP = 12.0
U_AUTHORITY = 25.0
MACRO_STEPS = 20
MICRO_STEPS = 10
MACRO_DT = 0.1
MICRO_DT = MACRO_DT / MICRO_STEPS
BASIN_TOL = 0.10
CONVEY_WINDOW = 5
CERT_WINDOW = 10

PARAMETER_RANGES: Dict[str, Tuple[float, float]] = {
    "alpha": (4.2, 4.2), "beta_int": (0.0, 1.0), "beta_ext": (0.0, 1.0), "k": (1.7, 1.7),
    "sigma_1": (0.38, 0.38), "delta": (0.01, 1.0), "gamma_1": (1.35, 1.35), "gamma_c": (1.0, 1.0),
    "lambda_0": (-2.0, 2.0), "lambda_1": (0.1, 3.0), "lambda_2": (0.0, 2.0), "c": (0.5, 5.0),
    "E_max": (1.0, 10.0), "omega_B": (0.1, 5.0), "Q_B": (0.5, 10.0), "alpha_s": (0.05, 0.25),
    "beta_s": (0.05, 0.25), "mu": (2.0, 6.0), "alpha_E": (4.2, 4.2), "alpha_U": (4.2, 4.2),
    "lambda_I": (0.5, 2.0), "lambda_U": (0.0, 0.5),
}
# alpha, k, gamma_1, alpha_U do not enter equations (1)-(8).


@dataclass
class State:
    E: float
    U: float
    I_U: float
    S: float
    B: float
    B_dot: float

    def as_tuple(self) -> Tuple[float, ...]:
        return (self.E, self.U, self.I_U, self.S, self.B, self.B_dot)


@dataclass
class Params:
    alpha: float = 4.2
    beta_int: float = 0.0
    beta_ext: float = 0.0
    k: float = 1.7
    sigma_1: float = 0.38
    delta: float = 0.5
    gamma_1: float = 1.35
    gamma_c: float = 1.0
    lambda_0: float = 0.0
    lambda_1: float = 1.0
    lambda_2: float = 0.5
    c: float = 1.0
    E_max: float = 2.0
    omega_B: float = 1.0
    Q_B: float = 2.5
    alpha_s: float = 0.12
    beta_s: float = 0.10
    mu: float = 4.0
    alpha_E: float = 4.2
    alpha_U: float = 4.2
    lambda_I: float = 1.0
    lambda_U: float = 0.1


# ----------------------------------------------------------------- equations
def v_eff(x: State, p: Params, t: float = 0.0) -> float:
    z = p.lambda_0 + p.lambda_1 * (x.U - 0.5) + p.lambda_2 * x.S
    return math.cos(0.5 * p.omega_B * t) * (p.c * math.tanh(z))


def phi(S: float, p: Params) -> float:
    return 0.5 * p.alpha_s * S * S + 0.25 * p.beta_s * S ** 3 - p.delta * S


def s_flow(S: float, p: Params) -> float:
    return p.delta - p.alpha_s * S - 0.75 * p.beta_s * S * S


def derivatives(x: State, p: Params, t: float, u: float = 0.0) -> State:
    v = v_eff(x, p, t)
    dE = -p.alpha_E * x.E + p.beta_int + p.beta_ext + v
    dU = p.mu * x.U * (1.0 - x.U * x.U) - dE / max(p.E_max, 1e-6) - p.lambda_U * x.U + u
    dI = (1.0 - x.U) - p.sigma_1 * x.E - p.delta * x.S - p.lambda_I * x.I_U
    dS = s_flow(x.S, p)
    dBd = p.gamma_c * p.delta * x.S - (p.omega_B / max(p.Q_B, EPS)) * x.B_dot - p.omega_B ** 2 * x.B
    return State(dE, dU, dI, dS, x.B_dot, dBd)


def _axpy(x: State, k: State, h: float) -> State:
    return State(x.E + h * k.E, x.U + h * k.U, x.I_U + h * k.I_U, x.S + h * k.S, x.B + h * k.B, x.B_dot + h * k.B_dot)


def rk4_step(x: State, p: Params, t: float, h: float, u: float = 0.0) -> State:
    k1 = derivatives(x, p, t, u)
    k2 = derivatives(_axpy(x, k1, 0.5 * h), p, t + 0.5 * h, u)
    k3 = derivatives(_axpy(x, k2, 0.5 * h), p, t + 0.5 * h, u)
    k4 = derivatives(_axpy(x, k3, h), p, t + h, u)
    c = h / 6.0
    return State(*(a + c * (b1 + 2 * b2 + 2 * b3 + b4) for a, b1, b2, b3, b4 in
                   zip(x.as_tuple(), k1.as_tuple(), k2.as_tuple(), k3.as_tuple(), k4.as_tuple())))


def bath_residual(prev: State, cur: State, nxt: State, p: Params, h: float) -> float:
    d2 = (nxt.B - 2.0 * cur.B + prev.B) / (h * h)
    dm = (cur.B - prev.B) / h
    return d2 + (p.omega_B / max(p.Q_B, EPS)) * dm + p.omega_B ** 2 * cur.B - p.gamma_c * p.delta * cur.S


# ----------------------------------------------------------------- controller
def control_command(x: State, p: Params, t: float, target: int) -> Tuple[float, float]:
    """Return (u, raw) for one micro step. raw is the unclipped command."""
    drift = derivatives(x, p, t, 0.0).U
    raw = -drift + KP * (float(target) - x.U)
    return max(-U_AUTHORITY, min(U_AUTHORITY, raw)), raw


def basin_sign(U: float) -> int:
    if abs(U - 1.0) <= BASIN_TOL:
        return 1
    if abs(U + 1.0) <= BASIN_TOL:
        return -1
    return 0


def nearest_basin_sign(U: float) -> int:
    return 1 if abs(U - 1.0) <= abs(U + 1.0) else -1


def macro_step(x: State, p: Params, t0: float, target: Optional[int],
               micro_steps: int = MICRO_STEPS, macro_dt: float = MACRO_DT) -> Tuple[State, Dict[str, float]]:
    """Advance one macro interval. target=None runs the plant with u=0 (observe)."""
    h = macro_dt / micro_steps
    t = t0
    u_abs = u_sq = u_peak = 0.0
    sat = 0
    for _ in range(micro_steps):
        if target is None:
            u = raw = 0.0
        else:
            u, raw = control_command(x, p, t, target)
        u_abs += abs(u) * h
        u_sq += u * u * h
        u_peak = max(u_peak, abs(u))
        sat += int(abs(raw) > U_AUTHORITY + EPS)
        x = rk4_step(x, p, t, h, u)
        t += h
    return x, {"u_abs": u_abs, "u_sq": u_sq, "u_peak": u_peak, "saturated": sat}


# ----------------------------------------------------------------- trajectory
@dataclass
class Result:
    final: State
    U_hist: List[float]
    target_sign: int
    born: int
    convey: int
    convey_start: int
    convey_confirm: int
    cert: int
    cert_start: int
    cert_complete: int
    max_streak: int
    actuator_abs_integral: float
    actuator_sq_integral: float
    actuator_peak: float
    actuator_saturated_periods: int


def simulate(x0: State, p: Params, target: Optional[int] = None, controlled: bool = True) -> Result:
    """Canonical 20-macro-step trajectory with CONVEY-5 / CERT-10 predicates.

    target defaults to the nearest basin of U0. controlled=False runs u=0.
    """
    tgt = nearest_basin_sign(x0.U) if target is None else int(target)
    b0 = basin_sign(x0.U)
    born = int(b0 != 0)
    streak = 1 if born else 0
    ssign = b0 if born else 0
    best = streak
    convey = cert = 0
    cs = cc = ts = tc = -1
    ua = usq = upk = 0.0
    nsat = 0
    x = x0
    hist = [x0.U]
    for m in range(1, MACRO_STEPS + 1):
        x, a = macro_step(x, p, (m - 1) * MACRO_DT, tgt if controlled else None)
        ua += a["u_abs"]; usq += a["u_sq"]; upk = max(upk, a["u_peak"]); nsat += a["saturated"]
        hist.append(x.U)
        b = basin_sign(x.U)
        if b:
            if b == ssign:
                streak += 1
            else:
                ssign, streak = b, 1
        else:
            ssign, streak = 0, 0
        best = max(best, streak)
        if not convey and streak >= CONVEY_WINDOW:
            convey, cs, cc = 1, m - CONVEY_WINDOW + 1, m
        if not cert and streak >= CERT_WINDOW:
            cert, ts, tc = 1, m - CERT_WINDOW + 1, m
    return Result(x, hist, tgt, born, convey, cs, cc, cert, ts, tc, best, ua, usq, upk, nsat)


def sample_state(rng) -> State:
    return State(float(rng.uniform(0.0, 1.0)), float(rng.uniform(-1.0, 1.0)), float(rng.uniform(0.0, 1.0)),
                 float(rng.uniform(-1.0, 1.0)), float(rng.uniform(-1.0, 1.0)), float(rng.uniform(-1.0, 1.0)))


def sample_params(rng) -> Params:
    return Params(**{k: float(rng.uniform(lo, hi)) for k, (lo, hi) in PARAMETER_RANGES.items()})


def s_roots(p: Params) -> Tuple[float, float]:
    """Roots of equation (6): S_minus < 0 < S_plus."""
    a = 0.75 * p.beta_s
    d = math.sqrt(p.alpha_s ** 2 + 4.0 * a * p.delta)
    return (-p.alpha_s - d) / (2.0 * a), (-p.alpha_s + d) / (2.0 * a)
