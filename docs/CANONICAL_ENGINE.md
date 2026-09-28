# Canonical engine declaration

One engine runs Omni-Compass, and every result in this repository comes from it. This page names it, gives its
equations exactly as the code computes them, and names every other form as a variant. Where any document, manual, chart
or filing states the equations differently, this page and the file it fingerprints are what the software runs.

## 1. The canonical engine: `symmetric_verified`

| | |
|---|---|
| Name | `symmetric_verified` (`omnicompass/configurations.py`, `DEFAULT`) |
| Code | `omnicompass/core.py` (Python), `cpp/src/core.cpp` (C++ twin, sealed in `results/SEAL.json`) |
| Fingerprint | SHA-256 of `omnicompass/core.py`, recorded in `results/PREREGISTRATION.json` and `RELEASE_MANIFEST.json`; checked by `verify.py` |
| Evidence | every simulation, benchmark, live Kubernetes run and GPU harness in this repository |

State: E (deviation), U (coherence), I_U (unmet-need integral), S (structural stress), B and B_dot (the bath).

```
v_eff  = cos(omega_B t / 2) · c · tanh(lambda_0 + lambda_1 (U − 0.5) + lambda_2 S)        (spinor closure, 720°)
dE/dt  = −alpha_E E + beta_int + beta_ext + v_eff
dU/dt  = mu U (1 − U²) − (dE/dt) / E_max − lambda_U U + u                                 (symmetric double well)
dI_U/dt = (1 − U) − sigma_1 E − delta S − lambda_I I_U
dS/dt  = delta − alpha_s S − (3/4) beta_s S²                                               (gradient of Phi)
dB/dt  = B_dot
dB_dot/dt = gamma_c delta S − (omega_B / Q_B) B_dot − omega_B² B
Phi(S) = alpha_s S² / 2 + beta_s S³ / 4 − delta S
```
u is the controller's command, `KP (target − U) − drift`, bounded by `U_AUTHORITY`; integration is RK4 with the
macro and micro steps of `omnicompass/core.py`.

## 2. Variants

### `printed_eight_line` (the printed chart)
Implemented in `omnicompass/configurations.py`, checked against the printed plate (`tests/test_engine_configurations.py`),
**not benchmarked**: no result in this repository comes from it.

```
v_eff  = c · tanh(lambda_0 + lambda_1 (U − U_t) + lambda_2 S)                             (no spinor factor)
dE/dt  = −alpha E + beta_int + beta_ext + v_eff
dU/dt  = alpha (1 − U) − (dE/dt) / E_max − k U (1 − U) + u                                 (logistic)
dI_U/dt = (1 − U) − sigma_1 E − delta S                                                    (no lambda_I term)
dS/dt, dB/dt, dB_dot/dt as in section 1
```

Differences from the canonical engine: logistic U instead of the symmetric double well; no spinor factor; a general
target U_t; no lambda_I damping; alpha in place of alpha_E. alpha_U and k enter the printed form; they do not enter the
canonical engine.

## 3. What would change this declaration

Promoting a variant to canonical needs, in one commit: the variant run through every harness beside the canonical
engine, its results reported next to the canonical results, this page and `RELEASE_MANIFEST.json` updated, and the
preregistration amended on record (`results/LOCK_AMENDMENTS.json`). Until then the canonical engine is
`symmetric_verified`.

## 4. Open mathematical items (from `docs/FORMAL_STATUS.md` and the handoff)

- A global stability proof of the forced six-state system is not closed. What is held: the isolated S-flow is the
  gradient of Phi; with the command unsaturated, dU/dt = KP (target − U), with V = e²/2 and dV/dt = −KP e² on that
  channel.
- Candidate routes: the Unified Circle Principle on a region; Theorem 5.6 of the Closed Structure, if its core maps onto
  (E, U, I_U, S, B).

## 5. For filings

Which form a patent or copyright filing claims as the principal embodiment is a decision for The Omni-Compass LLC and
its counsel. Whatever that decision, the software described by this repository runs the canonical engine of section 1,
and a filing that claims the printed form should name `symmetric_verified` as the embodiment that has been implemented
and tested, or the printed form should be benchmarked first (section 3).
