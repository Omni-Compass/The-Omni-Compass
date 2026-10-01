"""Mechanism of action: what the Omni-Compass equations actually do inside the governor, measured.

  1. linearisation   Jacobian of equations (1)-(7) at the operating point the governor lives at; eigenvalues give each
                     mode's time constant, in engine time and in governor decisions (the adapter advances engine time
                     0.1 per decision: omnicompass/adapter.py, Governor.step)
  2. who moves the   per decision the state changes twice: assimilation (the observation blended in with weight 0.339)
     state           and evolution (one macro step of the equations). Their sizes are measured on a real observation
                     stream (fleet plant, web vessel, fleet mode)
  3. the controller  whether equation (2)'s control input u is applied during governance
  4. compute         microseconds per governor decision
Writes results/MECHANISM_OF_ACTION.json.
"""
from __future__ import annotations

import json, math, sys, time
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass import adapter as A
from omnicompass.core import State, derivatives, macro_step

NAMES = ["E", "U", "I_U", "S", "B", "B_dot"]


def jacobian(x, p, t=0.0, h=1e-6):
    f0 = np.array(derivatives(x, p, t).as_tuple())
    J = np.zeros((6, 6))
    for j in range(6):
        v = list(x.as_tuple()); v[j] += h
        J[:, j] = (np.array(derivatives(State(*v), p, t).as_tuple()) - f0) / h
    return J


def record_stream(vessel="web", seed=101):
    """Observation stream a fleet-mode governor sees on the fleet plant (captured from a real run)."""
    from fleet import sim_slo
    from fleet.harness import make_scenario
    seen = []
    orig = A.Governor.step

    def spy(self, obs, conflicts):
        seen.append(dict(obs))
        return orig(self, obs, conflicts)
    A.Governor.step = spy
    try:
        sim_slo.run(make_scenario(vessel, seed), "omni_fleet")
    finally:
        A.Governor.step = orig
    return seen


def split(stream):
    p = replace(A.STACK_PARAMS)
    x = State(**vars(A.INITIAL_STATE)); t = 0.0
    d_obs, d_math = [], []
    for obs in stream:
        o = A.observe_vector(obs, 0)
        xa = A.assimilate(x, o, p)
        xn, _ = macro_step(xa, p, t, target=None)
        d_obs.append(np.abs(np.array(xa.as_tuple()) - np.array(x.as_tuple())))
        d_math.append(np.abs(np.array(xn.as_tuple()) - np.array(xa.as_tuple())))
        x, t = xn, t + 0.1
    return np.mean(d_obs, 0), np.mean(d_math, 0), x, p


def main():
    stream = record_stream()
    obs_move, math_move, x_op, p_op = split(stream)
    J = jacobian(x_op, p_op)
    ev = np.linalg.eigvals(J)
    modes = []
    for e in sorted(ev, key=lambda z: z.real):
        tau = (-1.0 / e.real) if e.real < 0 else float("inf")
        modes.append({"eigenvalue": [float(e.real), float(e.imag)], "time_constant_engine": tau,
                      "time_constant_decisions": tau / 0.1 if math.isfinite(tau) else None,
                      "period_decisions": (2 * math.pi / abs(e.imag) / 0.1) if abs(e.imag) > 1e-9 else None})
    g = A.Governor(law=A.mode_law("fleet")); g.set_mode(A.AUTOPILOT)
    t0 = time.perf_counter(); n = 0
    for obs in stream * 3:
        g.step(obs, 0); n += 1
    us = (time.perf_counter() - t0) / n * 1e6
    share = {k: {"assimilation": float(a), "equations": float(m), "equations_share": float(m / max(a + m, 1e-12))}
             for k, a, m in zip(NAMES, obs_move, math_move)}
    out = {"operating_point": dict(zip(NAMES, map(float, x_op.as_tuple()))),
           "forcing_at_operating_point": {"beta_int": p_op.beta_int, "beta_ext": p_op.beta_ext},
           "jacobian": J.tolist(), "modes": modes,
           "per_decision_movement": share,
           "engine_time_per_decision": 0.1, "assimilation_weight": A.ASSIMILATION,
           "controller_applied_in_governance": False,
           "controller_note": "Governor.step evolves with target=None: equation (2)'s input u is zero; the control law is "
                              "evaluated only to produce 'push', which gates capacity release",
           "microseconds_per_decision_python": us, "decisions_measured": n}
    (ROOT / "results/MECHANISM_OF_ACTION.json").write_text(json.dumps(out, indent=1))
    print("operating point:", {k: round(v, 3) for k, v in out["operating_point"].items()})
    print("modes (engine time constant -> decisions):")
    for m in modes:
        print(f"  lambda = {m['eigenvalue'][0]:+.3f}{m['eigenvalue'][1]:+.3f}i   tau = {m['time_constant_engine']:.3g} "
              f"-> {m['time_constant_decisions'] if m['time_constant_decisions'] is None else round(m['time_constant_decisions'], 1)} decisions"
              + (f", period {m['period_decisions']:.0f} decisions" if m["period_decisions"] else ""))
    print("mean movement per decision (assimilation vs equations):")
    for k, v in share.items():
        print(f"  {k:6} observation {v['assimilation']:.4f}  equations {v['equations']:.4f}  -> equations do {100*v['equations_share']:.0f}%")
    print(f"controller u applied during governance: {out['controller_applied_in_governance']}")
    print(f"compute: {us:.1f} microseconds per decision (Python)")


if __name__ == "__main__":
    main()
