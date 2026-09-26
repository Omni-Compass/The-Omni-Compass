"""Named engine configurations.

Default remains omnicompass.core (symmetric_verified). This module does not
replace it. printed_eight_line is the marketing-plate transcription.

  symmetric_verified  claim-2 / package core
    dE = -alpha_E E + beta_int + beta_ext + v_eff
    dU = mu U (1-U^2) - dE/E_max - lambda_U U + u
    dI = 1-U - sigma_1 E - delta S - lambda_I I_U
    v  = cos(omega_B t / 2) * c * tanh(lambda_0 + lambda_1 (U-0.5) + lambda_2 S)

  printed_eight_line  plate species (not the held-out evidence core)
    dE = -alpha E + beta_int + beta_ext + v_eff
    dU = alpha (1-U) - dE/E_max - k U (1-U) + u
    dI = 1-U - sigma_1 E - delta S
    v  = c * tanh(lambda_0 + lambda_1 (U-U_t) + lambda_2 S)
"""
from __future__ import annotations

import math
from typing import Callable

from .core import EPS, KP, U_AUTHORITY, Params, State, derivatives as core_derivatives, v_eff as core_v_eff


SYMMETRIC = "symmetric_verified"
PRINTED = "printed_eight_line"
DEFAULT = SYMMETRIC


def printed_v_eff(x: State, p: Params, t: float = 0.0, U_t: float = 0.5) -> float:
    z = p.lambda_0 + p.lambda_1 * (x.U - U_t) + p.lambda_2 * x.S
    return p.c * math.tanh(z)


def printed_derivatives(x: State, p: Params, t: float, u: float = 0.0, U_t: float = 0.5) -> State:
    v = printed_v_eff(x, p, t, U_t)
    dE = -p.alpha * x.E + p.beta_int + p.beta_ext + v
    dU = p.alpha * (1.0 - x.U) - dE / max(p.E_max, 1e-6) - p.k * x.U * (1.0 - x.U) + u
    dI = (1.0 - x.U) - p.sigma_1 * x.E - p.delta * x.S
    dS = p.delta - p.alpha_s * x.S - 0.75 * p.beta_s * x.S * x.S
    dBd = p.gamma_c * p.delta * x.S - (p.omega_B / max(p.Q_B, EPS)) * x.B_dot - p.omega_B ** 2 * x.B
    return State(dE, dU, dI, dS, x.B_dot, dBd)


def derivatives_for(name: str) -> Callable:
    if name == SYMMETRIC:
        return core_derivatives
    if name == PRINTED:
        return printed_derivatives
    raise ValueError(name)


def control_command_for(name: str, x: State, p: Params, t: float, target: float):
    deriv = derivatives_for(name)
    drift = deriv(x, p, t, 0.0).U
    raw = -drift + KP * (float(target) - x.U)
    return max(-U_AUTHORITY, min(U_AUTHORITY, raw)), raw


def describe(name: str) -> str:
    return {
        SYMMETRIC: "package / claim-2 cubic U; owns held-out evidence",
        PRINTED: "plate logistic U; executable; not the default",
    }[name]
