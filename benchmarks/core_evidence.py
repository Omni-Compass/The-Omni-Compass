# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Canonical 500-run population and counterfactual variants.

Variants on the identical population (seed 223387268):
  controlled         canonical: target = nearest basin of U0
  wrong_target       controller aimed at the opposite basin
  uncontrolled       u = 0 throughout
  controlled_mu0     canonical controller, double-well coefficient mu set to 0
Also: S-channel admissibility S0 >= S_minus(p), bath residual RMS, RK4 step refinement.
"""
import json, sys, math
from dataclasses import replace
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass import core as C

def main(out=ROOT / "results" / "core_evidence.json", seed=223387268, runs=500):
    rng = np.random.default_rng(seed)
    pop = [(C.sample_state(rng), C.sample_params(rng)) for _ in range(runs)]
    res = {}
    for name in ("controlled", "wrong_target", "uncontrolled", "controlled_mu0"):
        cv = ce = 0; peak = 0.0; sat = 0; confirm = []
        for x0, p in pop:
            pp = replace(p, mu=0.0) if name == "controlled_mu0" else p
            tgt = -C.nearest_basin_sign(x0.U) if name == "wrong_target" else None
            r = C.simulate(x0, pp, target=tgt, controlled=(name != "uncontrolled"))
            cv += r.convey; ce += r.cert; peak = max(peak, r.actuator_peak); sat += r.actuator_saturated_periods
            if r.convey: confirm.append(r.convey_confirm)
        res[name] = {"convey5": cv, "cert10": ce, "runs": runs, "actuator_peak": peak, "saturated_microsteps": sat,
                     "convey_confirm_step_counts": {str(k): int(v) for k, v in zip(*np.unique(confirm, return_counts=True))}}
    # closed-form prediction under exact cancellation: U_k = s + (U0 - s) exp(-KP * 0.1 k)
    hit = 0
    for x0, p in pop:
        s = C.nearest_basin_sign(x0.U); r = C.simulate(x0, p)
        Uk = [s + (x0.U - s) * math.exp(-C.KP * C.MACRO_DT * k) for k in range(C.MACRO_STEPS + 1)]
        first = next(k for k, u in enumerate(Uk) if abs(u - s) <= C.BASIN_TOL)
        hit += int((4 if first == 0 else first + 4) == r.convey_confirm)
    res["first_order_prediction_of_convey_step"] = {"matched": hit, "runs": runs}
    adm = [x0.S >= C.s_roots(p)[0] for x0, p in pop]
    res["s_admissibility"] = {"pass": int(sum(adm)), "runs": runs,
                              "min_margin": float(min(x0.S - C.s_roots(p)[0] for x0, p in pop))}
    rms = []
    for x0, p in pop[:100]:
        xs = [x0]; x = x0
        for m in range(200):
            u, _ = C.control_command(x, p, m * C.MICRO_DT, C.nearest_basin_sign(x0.U))
            x = C.rk4_step(x, p, m * C.MICRO_DT, C.MICRO_DT, u); xs.append(x)
        r = [C.bath_residual(xs[i - 1], xs[i], xs[i + 1], p, C.MICRO_DT) for i in range(1, len(xs) - 1)]
        rms.append(math.sqrt(sum(v * v for v in r) / len(r)))
    res["bath_residual_rms"] = {"median": float(np.median(rms)), "max": float(max(rms)), "runs": 100}
    x0, p = pop[0]
    def final(h):
        x = x0; n = int(round(2.0 / h))
        for m in range(n):
            u, _ = C.control_command(x, p, m * h, C.nearest_basin_sign(x0.U)); x = C.rk4_step(x, p, m * h, h, u)
        return np.array(x.as_tuple())
    ref = final(0.000625)
    res["rk4_refinement_run0"] = {str(h): float(np.max(np.abs(final(h) - ref))) for h in (0.02, 0.01, 0.005, 0.0025)}
    Path(out).write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
