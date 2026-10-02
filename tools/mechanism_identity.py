# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The mechanism's identity: M = (F, Theta, C, h, G, M_act, dt, A), one fingerprint per engine configuration.

  python3 tools/mechanism_identity.py           # write results/MECHANISM_IDENTITY.json
  python3 tools/mechanism_identity.py --check   # compare the code with the recorded identity (verify.py runs this)
  python3 tools/mechanism_identity.py --id      # the canonical mechanism id of the code as it stands (the GPU bench records it)

Each component is fingerprinted (SHA-256) from the source text of the functions that compute it, and Theta from the
values of every constant and parameter. The mechanism id is the SHA-256 of the eight component fingerprints in order,
so it changes exactly when a component changes, and changes in unrelated code (reports, docs) leave it alone.

  F       state law                 dx/dt = F(x, d, u; Theta): derivatives (+ v_eff, s_flow), per configuration
  Theta   parameters                Params defaults, PARAMETER_RANGES, KP, U_AUTHORITY, steps, windows, ASSIMILATION
  C       internal controller       u = clip(-f_U + KP (sigma - U), +-U_AUTHORITY), per configuration
  h       observation map           observe_vector, assimilate (omnicompass/adapter.py)
  G       authority law             Governor.step, AllocationLaw, mode_law (omnicompass/adapter.py)
  M_act   authority -> actuator     GPU power limit (omni_controller/gpu_governor.py: shield_limit, busy_gate,
                                    lock_decide, GpuGovernor.set_limit, GpuGovernor.step); Kubernetes (omni_controller/muscles.py)
  dt      execution contract        rk4_step, macro_step (u computed before each RK4 micro step, held through its four
                                    stages), MACRO_DT, MICRO_STEPS; the GPU decision interval
  A       admissibility / shield    omnicompass/shield.py (violations, enforce, ShieldLimits), shield_limit

Also records the frozen 500-fixture comparison of the two configurations (benchmarks/core_evidence.py population,
seed 223387268): executable both, not interchangeable. No new population is drawn.
"""
from __future__ import annotations

import argparse, hashlib, inspect, json, math, sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from omnicompass import core as C, configurations as K, adapter as A, shield as SH
from omni_controller import gpu_governor as GG, muscles as MU

OUT = ROOT / "results" / "MECHANISM_IDENTITY.json"
SEED, RUNS = 223387268, 500


def h_src(*objs):
    return hashlib.sha256("\n".join(inspect.getsource(o) for o in objs).encode()).hexdigest()


def h_val(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()


def theta():
    return {"Params_defaults": asdict(C.Params()), "PARAMETER_RANGES": C.PARAMETER_RANGES, "KP": C.KP,
            "U_AUTHORITY": C.U_AUTHORITY, "MACRO_STEPS": C.MACRO_STEPS, "MICRO_STEPS": C.MICRO_STEPS,
            "MACRO_DT": C.MACRO_DT, "BASIN_TOL": C.BASIN_TOL, "CONVEY_WINDOW": C.CONVEY_WINDOW,
            "CERT_WINDOW": C.CERT_WINDOW, "ASSIMILATION": A.ASSIMILATION,
            "gpu_governor_defaults": {k: v for k, v in vars(GG.parser().parse_args(["--smi", "x"])).items()
                                      if k not in ("smi", "audit", "kill_file", "latency_file", "baseline_file", "gpus")}}


def components(name):
    F = h_src(C.derivatives, C.v_eff, C.s_flow) if name == K.SYMMETRIC else h_src(K.printed_derivatives, K.printed_v_eff)
    Cc = h_src(C.control_command) if name == K.SYMMETRIC else h_src(K.control_command_for, K.derivatives_for)
    return {"F": F, "Theta": h_val(theta()), "C": Cc,
            "h": h_src(A.observe_vector, A.assimilate, A.clamp),
            "G": h_src(A.Governor, A.AllocationLaw, A.mode_law),
            "M_act": hashlib.sha256((h_src(GG.shield_limit, GG.busy_gate, GG.lock_decide, GG.GpuGovernor)
                                     + hashlib.sha256((ROOT / "omni_controller" / "muscles.py").read_bytes()).hexdigest()).encode()).hexdigest(),
            "dt": h_src(C.rk4_step, C._axpy, C.macro_step),
            "A": h_src(SH.ShieldLimits, SH.violations, SH.enforce, GG.shield_limit)}


def mech_id(comp):
    return hashlib.sha256("".join(comp[k] for k in ("F", "Theta", "C", "h", "G", "M_act", "dt", "A")).encode()).hexdigest()


def trajectory(name, x0, p):
    """The canonical 20-macro-step run for a configuration, with the same predicates as core.simulate. For
    symmetric_verified it is checked equal to core.simulate on every fixture."""
    deriv = K.derivatives_for(name)
    tgt = C.nearest_basin_sign(x0.U); h = C.MICRO_DT
    b0 = C.basin_sign(x0.U); streak = 1 if b0 else 0; ssign = b0; convey = cert = 0
    J = peak = 0.0; sat = 0; x = x0; finite = True
    for m in range(1, C.MACRO_STEPS + 1):
        t = (m - 1) * C.MACRO_DT                     # as core.macro_step: each macro interval starts on its own clock
        for _ in range(C.MICRO_STEPS):
            drift = deriv(x, p, t, 0.0).U
            raw = -drift + C.KP * (tgt - x.U); u = max(-C.U_AUTHORITY, min(C.U_AUTHORITY, raw))
            J += abs(u) * h; peak = max(peak, abs(u)); sat += abs(raw) > C.U_AUTHORITY + C.EPS
            k1 = deriv(x, p, t, u); k2 = deriv(C._axpy(x, k1, 0.5 * h), p, t + 0.5 * h, u)
            k3 = deriv(C._axpy(x, k2, 0.5 * h), p, t + 0.5 * h, u); k4 = deriv(C._axpy(x, k3, h), p, t + h, u)
            x = C.State(*(a + (h / 6.0) * (b1 + 2 * b2 + 2 * b3 + b4) for a, b1, b2, b3, b4 in
                          zip(x.as_tuple(), k1.as_tuple(), k2.as_tuple(), k3.as_tuple(), k4.as_tuple())))
            t += h
        finite = finite and all(math.isfinite(v) for v in x.as_tuple())
        b = C.basin_sign(x.U)
        streak, ssign = ((streak + 1, b) if b == ssign else (1, b)) if b else (0, 0)
        convey = convey or int(streak >= C.CONVEY_WINDOW); cert = cert or int(streak >= C.CERT_WINDOW)
    return {"finite": finite, "convey": convey, "cert": cert, "err": abs(x.U - tgt), "J_u": J, "peak": peak, "sat": sat, "final": x}


def comparison():
    rng = np.random.default_rng(SEED)
    pop = [(C.sample_state(rng), C.sample_params(rng)) for _ in range(RUNS)]
    out = {}
    for name in (K.SYMMETRIC, K.PRINTED):
        rs = [trajectory(name, x0, p) for x0, p in pop]
        if name == K.SYMMETRIC:
            for (x0, p), r in zip(pop, rs):
                ref = C.simulate(x0, p)
                assert ref.final.as_tuple() == r["final"].as_tuple() and ref.convey == r["convey"] and ref.cert == r["cert"], \
                    "the comparison loop differs from core.simulate"
        out[name] = {"finite": sum(r["finite"] for r in rs), "convey5": sum(r["convey"] for r in rs),
                     "cert10": sum(r["cert"] for r in rs), "runs": RUNS,
                     "mean_final_target_error": float(np.mean([r["err"] for r in rs])),
                     "mean_integrated_abs_u": float(np.mean([r["J_u"] for r in rs])),
                     "max_actuator_magnitude": float(max(r["peak"] for r in rs)),
                     "saturated_microsteps": int(sum(r["sat"] for r in rs))}
    return out


def build():
    cfgs = {}
    for name in (K.SYMMETRIC, K.PRINTED):
        comp = components(name)
        cfgs[name] = {"mechanism_id": mech_id(comp), "components": comp, "role": K.describe(name),
                      "canonical": name == K.DEFAULT}
    return {"definition": "M = (F, Theta, C, h, G, M_act, dt, A); state x = (E, U, I_U, S, B, B_dot); dx/dt = F(x, d, u; Theta)",
            "canonical": K.DEFAULT, "configurations": cfgs, "theta": theta(),
            "fixture_comparison": {"population": f"benchmarks/core_evidence.py, seed {SEED}, {RUNS} fixtures (frozen)",
                                   "results": comparison(),
                                   "reading": "both configurations are executable; they are not experimentally interchangeable "
                                              "(different final error and control effort). Evidence names the mechanism id that produced it."}}


def check():
    if not OUT.exists():
        return ["no results/MECHANISM_IDENTITY.json: run python3 tools/mechanism_identity.py"]
    rec = json.loads(OUT.read_text()); bad = []
    for name, c in rec["configurations"].items():
        now = components(name)
        for k, v in now.items():
            if c["components"][k] != v:
                bad.append(f"{name}: component {k} changed since the identity was recorded")
        if mech_id(now) != c["mechanism_id"]:
            bad.append(f"{name}: mechanism id changed")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--id", action="store_true", help="print the canonical mechanism id of the code as it stands")
    a = ap.parse_args(argv)
    if a.id:
        print(mech_id(components(K.DEFAULT))); return 0
    if a.check:
        bad = check(); print("\n".join(bad) if bad else "mechanism identity matches the code"); return 1 if bad else 0
    rec = build(); OUT.write_text(json.dumps(rec, indent=1) + "\n")
    for n, c in rec["configurations"].items():
        print(f"{n}: {c['mechanism_id']}")
    print(json.dumps(rec["fixture_comparison"]["results"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
