# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Computational checks behind docs/TRACKING_THEOREM.md, on the frozen 500-fixture population of
benchmarks/core_evidence.py (seed 223387268). No new population is drawn. Evidence class of every number here: V
(finite computational verification over these fixtures) — not a theorem, not a physical result.

  python3 tools/tracking_bounds.py      # writes results/TRACKING_BOUNDS.json

Checks, canonical engine (symmetric_verified), both with the target locked to the nearest basin and aimed wrong:
  drift bound      max |f_U| along every micro step against the analytic bound F_bar of theorem 2 (must be < U_AUTHORITY)
  saturation       micro steps with |raw| > U_AUTHORITY (occupancy of the saturated region)
  sampled data     e_(k+1) = rho e_k + d_k with rho = 1 - h KP (theorem 3): the largest |d_k| (epsilon_h), the
                   ultimate bound epsilon_h / (1 - rho), and whether |e_(k+1)| <= rho |e_k| + epsilon_h held at every step
  invariance       every micro step: x_k in A implies x_(k+1) in A, A the box of theorem 4 for that fixture
"""
from __future__ import annotations

import json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from omnicompass import core as C

SEED, RUNS = 223387268, 500
# theorem 2 over the whole declared box (PARAMETER_RANGES, E0 in [0, 1]): mu <= 6, |E| <= 7/4.2, |dE/dt| <= 4.2 |E| + 2 + 5,
# E_max >= 1, lambda_U <= 0.5, |U| <= 1.1
F_GLOBAL = 6 * 2 / (3 * math.sqrt(3)) + (4.2 * 7 / 4.2 + 7) / 1.0 + 0.5 * 1.1
OUT = ROOT / "results" / "TRACKING_BOUNDS.json"


def f_bar(p, E0):
    """Theorem 2's drift bound on the box |U| <= 1.1, E in the E box of this fixture:
    |f_U| <= mu * 2/(3 sqrt 3) + max|dE/dt| / E_max + 1.1 lambda_U."""
    lo, hi = e_box(p, E0)
    dE = max(abs(-p.alpha_E * lo + p.beta_int + p.beta_ext + p.c), abs(-p.alpha_E * hi + p.beta_int + p.beta_ext - p.c),
             abs(-p.alpha_E * lo + p.beta_int + p.beta_ext - p.c), abs(-p.alpha_E * hi + p.beta_int + p.beta_ext + p.c))
    return p.mu * 2.0 / (3.0 * math.sqrt(3.0)) + dE / p.E_max + 1.1 * p.lambda_U


def e_box(p, E0):
    """The E interval that equation (1) cannot leave: [(beta - c)/alpha_E, (beta + c)/alpha_E], widened to hold E0."""
    b = p.beta_int + p.beta_ext
    lo, hi = (b - p.c) / p.alpha_E, (b + p.c) / p.alpha_E
    return (lo, hi) if E0 is None else (min(lo, E0), max(hi, E0))


def run(x0, p, tgt):
    h = C.MICRO_DT; rho = 1.0 - h * C.KP
    e_lo, e_hi = e_box(p, x0.E)
    s_minus, s_plus = C.s_roots(p)
    s_lo, s_hi = min(x0.S, s_plus), max(x0.S, s_plus)
    e0 = x0.U - tgt
    out = {"fU_max": 0.0, "sat": 0, "d_max": 0.0, "steps": 0, "inv_fail": 0, "sign_flip": 0, "e_grew": 0}
    x = x0
    for m in range(C.MACRO_STEPS):
        t = m * C.MACRO_DT
        for _ in range(C.MICRO_STEPS):
            fU = C.derivatives(x, p, t, 0.0).U
            u, raw = C.control_command(x, p, t, tgt)
            out["fU_max"] = max(out["fU_max"], abs(fU)); out["sat"] += abs(raw) > C.U_AUTHORITY + C.EPS
            xn = C.rk4_step(x, p, t, h, u)
            e, en = x.U - tgt, xn.U - tgt
            out["d_max"] = max(out["d_max"], abs(en - rho * e))
            out["sign_flip"] += (e != 0 and en != 0 and (e > 0) != (en > 0))
            out["e_grew"] += abs(en) > abs(e) + 1e-15
            inside = lambda z: (e_lo - 1e-12 <= z.E <= e_hi + 1e-12 and abs(z.U - tgt) <= abs(e0) + 1e-12
                                and s_lo - 1e-12 <= z.S <= s_hi + 1e-12)
            out["inv_fail"] += inside(x) and not inside(xn)
            out["steps"] += 1
            x = xn; t += h
    return out


def main():
    rng = np.random.default_rng(SEED)
    pop = [(C.sample_state(rng), C.sample_params(rng)) for _ in range(RUNS)]
    h = C.MICRO_DT; rho = 1.0 - h * C.KP
    res = {"population": f"benchmarks/core_evidence.py, seed {SEED}, {RUNS} fixtures", "evidence_class": "V",
           "rho": rho, "h": h, "KP": C.KP, "U_AUTHORITY": C.U_AUTHORITY}
    for case, flip in (("nearest_target", 1), ("wrong_target", -1)):
        rs, fb = [], []
        for x0, p in pop:
            tgt = flip * C.nearest_basin_sign(x0.U)
            rs.append(run(x0, p, tgt)); fb.append(f_bar(p, x0.E))
        eps = max(r["d_max"] for r in rs)
        res[case] = {
            "drift_max_observed": max(r["fU_max"] for r in rs),
            "drift_bound_F_bar_max": max(fb), "F_bar_global": F_GLOBAL,
            "drift_within_bound_all": all(r["fU_max"] <= b + 1e-9 for r, b in zip(rs, fb)),
            "F_bar_below_U_AUTHORITY_all": all(b < C.U_AUTHORITY for b in fb),
            "saturated_microsteps": sum(r["sat"] for r in rs), "microsteps": sum(r["steps"] for r in rs),
            "epsilon_h": eps, "ultimate_bound": eps / (1.0 - rho), "basin_tol": C.BASIN_TOL,
            "ultimate_bound_inside_basin": eps / (1.0 - rho) < C.BASIN_TOL,
            "error_sign_changes": sum(r["sign_flip"] for r in rs), "error_growth_steps": sum(r["e_grew"] for r in rs),
            "invariance_failures": sum(r["inv_fail"] for r in rs)}
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    if __name__ == "__main__":
        print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    main()
