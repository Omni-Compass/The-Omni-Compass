"""The engine's composite storage: the ledger that closes the circle.

Ported exactly from the engine source (composite_practical_lyapunov_value and its bath matrix, weights and S rest point,
docs/handoff/mathematics/omni_compass_engine_source_c527df2d.py); tests/test_core_parity.py checks it against that
source on 5,000 random states. The frozen engine (omnicompass/core.py) is not touched.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

from .core import EPS, Params, State, phi


def stable_S(p: Params) -> float:
    """S*, the stable rest of the axle: the root of delta - alpha_s S - (3/4) beta_s S^2 = 0 where the flow bends back."""
    a, b, c = 0.75 * p.beta_s, p.alpha_s, -p.delta
    if abs(a) <= EPS:
        return p.delta / max(p.alpha_s, EPS)
    disc = max(0.0, b * b - 4.0 * a * c)
    for r in ((-b + math.sqrt(disc)) / (2.0 * a), (-b - math.sqrt(disc)) / (2.0 * a)):
        if -p.alpha_s - 1.5 * p.beta_s * r < 0.0:
            return r
    raise RuntimeError("no stable S rest point")


def bath_P(p: Params) -> Tuple[float, float, float]:
    """(p11, p12, p22) of the positive-definite P solving A_B^T P + P A_B = -I for the bath (7)."""
    w = max(abs(p.omega_B), EPS); damp = max(w / max(abs(p.Q_B), EPS), EPS)
    p12 = 1.0 / (2.0 * w * w); p22 = (p12 + 0.5) / damp; p11 = damp * p12 + w * w * p22
    return p11, p12, p22


def composite_weights(p: Params) -> Dict[str, float]:
    alpha_s, beta_s = max(p.alpha_s, EPS), max(p.beta_s, EPS)
    p11, p12, p22 = bath_P(p)
    g = p.gamma_c * p.delta
    pg = (p12 * g, p22 * g)
    m_floor = alpha_s / 2.0
    return {"a_U": 1.0, "b_W": 1.0 / (2.0 * max(p.mu, EPS)), "c_E": 1.0 / max(p.alpha_E, EPS),
            "w_I": 1.0 / max(p.lambda_I, EPS), "w_S": (pg[0] ** 2 + pg[1] ** 2 + 0.25) / (m_floor * m_floor),
            "d_B": 1.0, "S_floor": -alpha_s / (3.0 * beta_s)}


def composite_V(x: State, p: Params, sigma: int = 1) -> Dict[str, float]:
    """The composite storage of the whole engine, the ledger that closes the circle:
    V = a_U (U - sigma)^2 / 2 + b_W W(U) + c_E E^2 / 2 + w_S (Phi(S) - Phi(S*)) + w_I I_U^2 / 2 + d_B z^T P z / 2,
    z = (B - B*, B_dot), B* = gamma_c delta S* / omega_B^2, W(U) = mu (U^2 - 1)^2 / 4."""
    sig = 1.0 if sigma >= 0 else -1.0
    w = composite_weights(p); s_star = stable_S(p)
    b_star = p.gamma_c * p.delta / max(abs(p.omega_B), EPS) ** 2 * s_star
    p11, p12, p22 = bath_P(p)
    z0, z1 = x.B - b_star, x.B_dot
    parts = {"V_U": 0.5 * w["a_U"] * (x.U - sig) ** 2, "V_W": w["b_W"] * 0.25 * p.mu * (x.U * x.U - 1.0) ** 2,
             "V_E": 0.5 * w["c_E"] * x.E ** 2, "V_S": w["w_S"] * (phi(x.S, p) - phi(s_star, p)),
             "V_I": 0.5 * w["w_I"] * x.I_U ** 2, "V_B": 0.5 * w["d_B"] * (p11 * z0 * z0 + 2 * p12 * z0 * z1 + p22 * z1 * z1)}
    return {"V": sum(parts.values()), **parts, "S_star": s_star, "B_star": b_star}
