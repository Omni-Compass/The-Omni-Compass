# The tracking theorem: what the U channel provably does, and what it does not

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

This page proves the internal tracking result of the canonical engine (`symmetric_verified`, mechanism id in
`results/MECHANISM_IDENTITY.json`) in four steps, from the continuous law to the code as executed. Each statement
carries one evidence class (see `docs/EVIDENCE_LEDGER.md`): **T** proved here, **V** checked by computation over a
finite, frozen set (`tools/tracking_bounds.py` → `results/TRACKING_BOUNDS.json`).

What this page establishes is **internal**: inside the declared model, the controller conveys U to its target
sigma. It does not establish that sigma is the right target for any outside plant, that the telemetry map is right,
that any actuator mapping (HPA, GPU, CPU) is right, any energy saving, production performance, or stability of the
whole forced six-state system. Target correctness and target conveyance are separate obligations; this page carries
only the second.

## Setting

U channel of equation (2): `dU/dt = f_U(x, t) + u`, with the uncontrolled drift

    f_U(x, t) = mu U (1 − U²) − (dE/dt) / E_max − lambda_U U

and the bounded cancellation-plus-proportional controller (`omnicompass/core.py`, `control_command`)

    u = sat(−f_U(x, t) + KP (sigma − U)),   sat(v) = max(−u_max, min(u_max, v)),   KP = 12, u_max = U_AUTHORITY = 25.

Tracking error `e = U − sigma`, sigma in {−1, +1}.

## Theorem 1 (T). Unsaturated tracking

On the unsaturated region `Omega_unsat = { x : |−f_U(x, t) − KP e| <= u_max }`, `de/dt = −KP e`. Along any interval
spent in `Omega_unsat`, `e(t) = e(t0) exp(−KP (t − t0))`, and `V = e²/2` satisfies `dV/dt = −KP e² < 0` for `e ≠ 0`.

*Proof.* Inside `Omega_unsat` the saturation is inactive, so `dU/dt = f_U − f_U + KP (sigma − U) = −KP e`; since sigma
is constant, `de/dt = dU/dt`. The solution and `dV/dt = e de/dt = −KP e²` follow. ∎

This is a statement about intervals inside `Omega_unsat` only; it is not global convergence.

## Theorem 2 (T). The saturated case, under a declared drift bound

**Assumption D.** Along the trajectory, `|f_U(x(t), t)| <= F_bar < u_max`.

Under D:
1. If saturation is active with `e < 0`, then `u = +u_max` and `de/dt = f_U + u_max >= u_max − F_bar > 0`; symmetrically
   for `e > 0`. So `dV/dt <= −(u_max − F_bar) |e| < 0` wherever saturation is active.
2. With Theorem 1, `V` is strictly decreasing wherever `e ≠ 0`, saturated or not; `e` never changes sign (at `e = 0`
   the command is unsaturated because `F_bar < u_max`, so `e = 0` is an equilibrium of the error dynamics).
3. Any saturated stretch ends within `(|e(t0)| − e*) / (u_max − F_bar)` time units, `e* = (u_max − F_bar) / KP`; the
   ball `|e| <= e*` lies inside `Omega_unsat` and is forward invariant, and inside it the decay is exponential at rate KP.

*Proof of 1.* Saturation with `u = +u_max` means `−f_U − KP e > u_max`, so `−KP e > u_max + f_U >= u_max − F_bar > 0`,
so `e < 0`, and `de/dt = f_U + u_max >= u_max − F_bar`. The other side is symmetric. 2 and 3 follow from 1 and
Theorem 1, and `|−f_U − KP e| <= F_bar + KP |e| <= u_max` on the ball. ∎

**Where D holds (T).** On the declared box — parameters in `PARAMETER_RANGES`, `E0` in [0, 1], `|U| <= 1.1` — equation
(1) keeps E in `[(beta − c)/alpha_E, (beta + c)/alpha_E]` widened to hold E0 (the right side of (1) points inward at
both ends, because `|v_eff| <= c`), so `|E| <= 7/4.2`, `|dE/dt| <= 4.2·|E| + 2 + 5 <= 14`, and

    F_bar = 6 · 2/(3√3) + 14 / 1 + 0.5 · 1.1 = 16.86 < 25 = u_max.

Because e keeps its sign and `|e|` does not grow (continuous time), U stays between U0 and sigma, so `|U| <= 1` and the
box is self-consistent for the nearest-basin target. **Theorem 2 therefore holds globally over the declared box, in
continuous time.** The actuator can still saturate: `|raw| <= F_bar + KP |e0|` can exceed 25 when `|e0|` is near 1.

**Checked (V).** Over the 500 frozen fixtures: observed `max |f_U|` = 6.84 (nearest target), 7.01 (wrong target), each
under that fixture's own bound (max 8.99) and under 16.86; saturated micro steps 0 of 100 000 (nearest target), 5 of
100 000 (wrong target).

## Theorem 3 (T with a computed constant). The executed sampled-data controller

The code does not run the continuous law. Per micro step `h = MICRO_DT = 0.01`, it computes `u_k` from `x_k`, holds it
through the four stages of one RK4 step (zero-order hold), and takes `x_(k+1) = F_h(x_k, u_k)`. There is no overwrite of U
after the step, no projection onto a basin, no state replacement.

Integrating the U equation over one held interval,

    e_(k+1) = e_k + h (f_U(x_k) + u_k) + ∫_(t_k)^(t_k+h) (f_U(x(t)) − f_U(x_k)) dt + tau_k

with `tau_k` the RK4 truncation error. Unsaturated, `f_U(x_k) + u_k = −KP e_k`, so

    e_(k+1) = rho e_k + d_k,   rho = 1 − h KP = 0.88,   |d_k| <= (h²/2) sup|df_U/dt| + |tau_k| =: epsilon_h.

Then by induction `|e_k| <= rho^k |e_0| + (1 − rho^k)/(1 − rho) · epsilon_h`, and the error enters and stays in the
neighbourhood `|e| <= epsilon_h / (1 − rho)`.

The proof above is exact given epsilon_h. **epsilon_h itself is computed, not proved (V):** the largest `|d_k|` over
every micro step of the 500 frozen fixtures is 0.00378 (nearest target), giving the ultimate bound 0.0315, inside
`BASIN_TOL` = 0.10 that CONVEY-5 and CERT-10 test. With the target aimed wrong, epsilon_h = 0.0243 (dominated by the
long transient, which includes the 5 saturated steps) and the bound 0.20 is wider than the basin — a conservative
bound; the fixtures still certify 500 of 500.

What the discrete execution does **not** inherit: the continuous monotone decay. Within the band, `|e|` grew on 27 061
of 100 000 micro steps and e changed sign 747 times — the sampled controller dithers inside `epsilon_h / (1 − rho)`.

**CONVEY and CERT.** They are dwell checks against a declared neighbourhood (`|U − sigma| <= 0.10` for 5 and 10
consecutive macro steps). Theorem 3 says why they pass when the bound sits inside the neighbourhood. They are not an
external certification.

## Theorem 4 (T continuous; V discrete). Admissibility

Admissible set for a fixture with parameters p and initial state x0:

    A = { x : E in [E_lo, E_hi],  |U − sigma| <= |U0 − sigma|,  S between S0 and S_plus(p) }

`E_lo, E_hi` as in Theorem 2; `S_plus` the stable root of equation (6).

- **Continuous (T).** A is forward invariant: E by the inward-pointing field at both ends; U by Theorem 2; S because
  equation (6) is the one-dimensional gradient flow of Phi, monotone toward `S_plus` from any `S0 > S_minus`
  (`s_admissibility` in `results/core_evidence.json`: 500 of 500 fixtures start above `S_minus`).
- **Discrete (V).** For the executed map `F_h(x, C(x))`, every micro step of every fixture: `x_k in A` implied
  `x_(k+1) in A` — 0 failures in 100 000 steps, target nearest or wrong. This is a finite verification on the frozen
  fixtures, not a proof over the box. An interval-arithmetic proof over the whole box is **open (O)**.

## What remains open (O)

- Global stability of the forced six-state system (E, I_U, S, B are not all covered above).
- A proved (not computed) epsilon_h over the declared box, and discrete invariance over the box.
- The inheritance / intertwining residual against an outside plant: instrumented (`tools/gpu_reps.py`,
  representation fidelity), not yet measured on a real card.
- The printed configuration (`printed_eight_line`) is not covered by this page: its U drift is logistic, not the
  double well, and needs its own bound (`docs/CANONICAL_ENGINE.md`).
