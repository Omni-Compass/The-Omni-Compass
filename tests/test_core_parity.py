# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""omnicompass.core vs reference engine functions and the 500 frozen fixtures."""
import csv, importlib.util, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass import core as C

KEYS = ("E", "U", "I_U", "S", "B", "B_dot")


def load_engine():
    import shutil, tempfile
    p = Path(tempfile.mkdtemp()) / "omni_compass_reference_engine.py"
    shutil.copy(ROOT / "reference" / "omni_compass_reference_engine.py", p)
    spec = importlib.util.spec_from_file_location("oc_ref", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["oc_ref"] = m
    spec.loader.exec_module(m)
    return m


def main():
    E = load_engine()
    rng = np.random.default_rng(7)
    worst = 0.0
    for _ in range(20000):
        xs = C.sample_state(rng); ps = C.sample_params(rng)
        t = float(rng.uniform(0, 3)); u = float(rng.uniform(-25, 25))
        ex = E.OCState(**xs.__dict__); ep = E.OCParameters(**ps.__dict__)
        a = C.derivatives(xs, ps, t, u).as_tuple()
        b = tuple(getattr(E.oc_derivatives(ex, ep, t, u), k) for k in KEYS)
        worst = max(worst, max(abs(i - j) for i, j in zip(a, b)))
        a = C.rk4_step(xs, ps, t, 0.01, u).as_tuple()
        b = tuple(getattr(E.rk4_step(ex, ep, t, 0.01, u), k) for k in KEYS)
        worst = max(worst, max(abs(i - j) for i, j in zip(a, b)))
        worst = max(worst, abs(C.derivatives(xs, ps, t, 0.0).U - E.raw_drift_U(ex, ep, t)))
    print(f"engine function parity (20,000 random cases): max |diff| = {worst:.3e}")
    assert worst <= 1e-12

    r1 = np.random.default_rng(223387268); r2 = np.random.default_rng(223387268)
    for _ in range(500):
        a = C.sample_state(r1); pa = C.sample_params(r1)
        b = E.sample_initial_state(r2); pb = E.sample_parameters(r2)
        assert a.__dict__ == b.__dict__ and pa.__dict__ == pb.__dict__
    print("sampling parity (seed 223387268): 500/500 identical")

    ins = list(csv.DictReader(open(ROOT / "fixtures" / "current_500_inputs.csv")))
    exp = list(csv.DictReader(open(ROOT / "fixtures" / "current_500_expected.csv")))
    mx = 0.0; mism = 0
    for i, e in zip(ins, exp):
        x0 = C.State(*(float(i[k]) for k in ("E0", "U0", "I0", "S0", "B0", "Bdot0")))
        p = C.Params(**{f.name: float(i[f.name]) for f in C.fields(C.Params)})
        r = C.simulate(x0, p)
        ints = dict(target_sign=r.target_sign, born=r.born, convey=r.convey, convey_start=r.convey_start,
                    convey_confirm=r.convey_confirm, cert=r.cert, cert_start=r.cert_start,
                    cert_complete=r.cert_complete, max_streak=r.max_streak,
                    actuator_saturated_periods=r.actuator_saturated_periods)
        flts = dict(zip(KEYS, r.final.as_tuple()))
        flts.update(actuator_abs_integral=r.actuator_abs_integral, actuator_sq_integral=r.actuator_sq_integral,
                    actuator_peak=r.actuator_peak, **{f"U_{k}": v for k, v in enumerate(r.U_hist)})
        for k, v in ints.items():
            mism += int(int(e[k]) != v)
        for k, v in flts.items():
            ev = float(e[k]); d = abs(ev - v); mx = max(mx, d)
            mism += int(d > 5e-12 and d / max(abs(ev), 1e-300) > 5e-11)
    print(f"fixture parity (500 frozen fixtures): max |diff| = {mx:.3e}, mismatches = {mism}")
    assert mism == 0
    # the composite storage (the ledger that closes the circle) against the reference certificate
    rng = np.random.default_rng(11); worst = 0.0
    for _ in range(5000):
        xs = C.sample_state(rng); ps = C.sample_params(rng); sg = 1 if rng.uniform() < 0.5 else -1
        try:
            ref = E.composite_practical_lyapunov_value(E.OCState(**xs.__dict__), E.OCParameters(**ps.__dict__), sg)
        except RuntimeError:
            continue
        from omnicompass.storage import composite_V
        got = composite_V(xs, ps, sg)
        for k in ("V", "V_U", "V_W", "V_E", "V_S", "V_I", "V_B"):
            worst = max(worst, abs(got[k] - ref[k]) / max(1.0, abs(ref[k])))
    print(f"composite storage parity (5000 states): max rel diff {worst:.2e}")
    assert worst <= 1e-9
    print("PASS test_core_parity")


if __name__ == "__main__":
    main()
