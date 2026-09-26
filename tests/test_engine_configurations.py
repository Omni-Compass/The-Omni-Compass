"""Identity of named cores. Does not promote printed_eight_line to default."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omnicompass.configurations import (
    PRINTED,
    SYMMETRIC,
    control_command_for,
    derivatives_for,
    printed_derivatives,
)
from omnicompass.core import KP, U_AUTHORITY, Params, State, derivatives


def _rand_state(rng):
    return State(
        E=rng.uniform(0.0, 1.4),
        U=rng.uniform(-0.9, 0.9),
        I_U=rng.uniform(0.0, 1.2),
        S=rng.uniform(-0.8, 0.8),
        B=rng.uniform(-0.5, 0.5),
        B_dot=rng.uniform(-0.4, 0.4),
    )


def _rand_params(rng):
    return Params(
        alpha=rng.uniform(3.0, 5.0),
        beta_int=rng.uniform(0.0, 0.8),
        beta_ext=rng.uniform(0.0, 0.8),
        k=rng.uniform(1.0, 2.2),
        sigma_1=rng.uniform(0.2, 0.6),
        delta=rng.uniform(0.2, 0.9),
        gamma_c=1.0,
        lambda_0=rng.uniform(-1.0, 1.0),
        lambda_1=rng.uniform(0.4, 2.0),
        lambda_2=rng.uniform(0.1, 1.5),
        c=rng.uniform(0.6, 2.0),
        E_max=rng.uniform(1.2, 4.0),
        omega_B=rng.uniform(0.4, 2.0),
        Q_B=rng.uniform(1.0, 4.0),
        alpha_s=rng.uniform(0.08, 0.2),
        beta_s=rng.uniform(0.08, 0.2),
        mu=rng.uniform(2.5, 5.0),
        alpha_E=rng.uniform(3.0, 5.0),
        lambda_I=rng.uniform(0.5, 1.5),
        lambda_U=rng.uniform(0.0, 0.4),
    )


def test_symmetric_is_core():
    rng = random.Random(7)
    for _ in range(1000):
        x, p, t, u = _rand_state(rng), _rand_params(rng), rng.uniform(0, 4), rng.uniform(-2, 2)
        a = derivatives(x, p, t, u)
        b = derivatives_for(SYMMETRIC)(x, p, t, u)
        assert a.as_tuple() == b.as_tuple()


def test_printed_matches_plate_terms():
    rng = random.Random(11)
    for _ in range(1000):
        x, p, t = _rand_state(rng), _rand_params(rng), rng.uniform(0, 3)
        U_t = 0.5
        v = p.c * math.tanh(p.lambda_0 + p.lambda_1 * (x.U - U_t) + p.lambda_2 * x.S)
        dE = -p.alpha * x.E + p.beta_int + p.beta_ext + v
        dU = p.alpha * (1.0 - x.U) - dE / max(p.E_max, 1e-6) - p.k * x.U * (1.0 - x.U)
        dI = (1.0 - x.U) - p.sigma_1 * x.E - p.delta * x.S
        got = printed_derivatives(x, p, t, 0.0, U_t)
        assert abs(got.E - dE) < 1e-12
        assert abs(got.U - dU) < 1e-12
        assert abs(got.I_U - dI) < 1e-12
        assert abs(got.S - (p.delta - p.alpha_s * x.S - 0.75 * p.beta_s * x.S * x.S)) < 1e-12


def test_controller_cancels_drift_when_unsaturated():
    rng = random.Random(13)
    n_ok = 0
    for name in (SYMMETRIC, PRINTED):
        for _ in range(500):
            x, p, t = _rand_state(rng), _rand_params(rng), rng.uniform(0, 2)
            target = 1.0
            u, raw = control_command_for(name, x, p, t, target)
            if abs(raw) >= U_AUTHORITY:
                continue
            dU = printed_derivatives(x, p, t, u).U if name == PRINTED else derivatives(x, p, t, u).U
            expect = KP * (target - x.U)
            assert abs(dU - expect) < 1e-9
            n_ok += 1
    assert n_ok > 100


def main():
    test_symmetric_is_core()
    print("PASS  symmetric_verified is the existing core")
    test_printed_matches_plate_terms()
    print("PASS  printed_eight_line matches the plate")
    test_controller_cancels_drift_when_unsaturated()
    print("PASS  unsaturated control leaves dU = KP (target-U)")
    print("PASS test_engine_configurations")


if __name__ == "__main__":
    main()
