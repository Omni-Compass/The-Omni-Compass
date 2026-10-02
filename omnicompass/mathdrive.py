# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Math-driven actuation: the Omni-Compass equations move the system directly.

The frozen governor (adapter.Governor) evolves the equations open-loop (u = 0) and reads only a few derived numbers.
Here the equations are closed-loop and their own quantities ARE the actuator commands. No equation is changed; the
integrator, parameters and observation map are the frozen ones (omnicompass/core.py, omnicompass/adapter.py).

Per decision
  1. sense      x <- assimilate(x, observe_vector(telemetry))                       (the frozen observation map)
  2. evolve     x <- macro_step(x, target = +1, macro_dt = clock)                   equations (1)-(7) with equation
                (2)'s controller ON: u = clip(-f_U(x) + 12 (1 - U), -25, 25) holds the healthy basin U = +1
  3. read the   effort  w = integral |u| dt / (25 clock)   in [0, 1]: how hard the math had to work to stay healthy
     math       need    I_U                                 equation (3): unrelieved need, slow memory
                tide    B, B_dot                            equation (7): the bath, second order, anticipates
                drive   v_eff                               equation (4): the tanh-bounded drive
  4. actuate    capacity   n = ceil(fit (1 + g_w w + g_I max(0, I_U) + g_B max(0, B_dot))) machines
                           (released one at a time only while w <= w_release: the math reports calm)
                pods       HPA target rho = clamp(rho0 - k_w w - k_I max(0, I_U), rho_min, rho0)
                power      cap = clamp(1 - g_cap max(0, B) + 2 w, cap_min, 1)   (the bath lowers power only when calm)
  clock: engine time advanced per decision. It sets how fast the math moves relative to the system: the bath's
  natural period is 2 pi / omega_B = 6.28 engine units, i.e. 6.28 / clock decisions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from omnicompass.adapter import STACK_PARAMS, INITIAL_STATE, observe_vector, assimilate
from omnicompass.core import State, macro_step, v_eff, U_AUTHORITY


@dataclass(frozen=True)
class MathLaw:
    clock: float = 0.1
    g_w: float = 1.0
    g_I: float = 0.3
    g_B: float = 0.5
    w_release: float = 0.02
    dwell: int = 3
    rho0: float = 0.70
    rho_min: float = 0.50
    k_w: float = 0.5
    k_I: float = 0.1
    g_cap: float = 0.0
    cap_min: float = 0.8


class MathDrive:
    def __init__(self, law: MathLaw = MathLaw()):
        self.law = law
        self.p = replace(STACK_PARAMS)
        self.x = State(**vars(INITIAL_STATE))
        self.t = 0.0
        self.calm = 0
        self.w = 0.0

    def step(self, obs, n, requests, cores_per_node):
        """Returns (hpa_target, node_target, power_cap, readout)."""
        L = self.law
        o = observe_vector(obs, 0)
        xa = assimilate(self.x, o, self.p)
        self.x, stats = macro_step(xa, self.p, self.t, target=+1, macro_dt=L.clock)
        self.t += L.clock
        w = min(1.0, stats["u_abs"] / (U_AUTHORITY * L.clock))
        self.w = w
        x = self.x
        need = max(0.0, x.I_U); tide = max(0.0, x.B_dot)
        fit = requests / cores_per_node
        want = math.ceil(fit * (1.0 + L.g_w * w + L.g_I * need + L.g_B * tide) - 1e-9)
        tgt = n
        if want > n:
            tgt = want; self.calm = 0
        elif want < n:
            self.calm = self.calm + 1 if w <= L.w_release else 0
            if self.calm >= L.dwell:
                tgt = n - 1; self.calm = 0
        else:
            self.calm = 0
        rho = min(L.rho0, max(L.rho_min, L.rho0 - L.k_w * w - L.k_I * need))
        cap = min(1.0, max(L.cap_min, 1.0 - L.g_cap * max(0.0, x.B) + 2.0 * w))
        return rho, int(tgt), cap, {"w": w, "I_U": x.I_U, "B": x.B, "B_dot": x.B_dot, "U": x.U, "E": x.E,
                                    "v_eff": v_eff(x, self.p, self.t)}
