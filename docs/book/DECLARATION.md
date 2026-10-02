# The Canonical Declaration

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../../LICENSE).

Every report the engine has ever produced opens with the same declaration. It is the birth certificate of the
mechanism: what the engine is, which equations it runs, what every symbol means, which parameters it samples, how a
run is born, conveyed and certified, and what the engine is allowed to say about itself. This chapter sets it down in
full so that anyone who reads the rest of this book can always come back to the source.

## The identity of the engine

The Omni-Compass Unified Governing Convergence Control Core Engine. One canonical eight-line mathematical core,
called Piece I, integrated by fourth-order Runge-Kutta (RK4) and exercised by Monte Carlo. Around that core sit the
benchmark suites: the public enterprise manager mechanism benchmark, the one-stack-normalized global megastack,
fragmented stack governance over matched scenarios, and the enterprise evidence suite covering cause, fail-safe,
scale, muscle, security and economics. All of them run on bare metal, on premises, private, public, hybrid and edge
alike, because the core does not care where it runs.

## The equation form (authoritative, eight lines)

    (1) dE/dt   = -α_E E + β_int(t) + β_ext(t) + v_eff
    (2) dU/dt   = μ U(1 - U²) - (dE/dt)/E_max - λ_U U + u,      |u| ≤ U_AUTHORITY
    (3) dI_U/dt = 1 - U - σ₁ E - δ S - λ_I I_U
    (4) v_eff   = χ(t) c · tanh(λ₀ + λ₁(U - U_t) + λ₂ S),       χ(t) = cos(ω_B t / 2)
    (5) Φ(S)    = ½ α_s S² + ¼ β_s S³ - δ S
    (6) dS/dt   = F_state(S) = -∂Φ(S)/∂S = δ - α_s S - ¾ β_s S²
    (7) B'' + (ω_B / Q_B) B' + ω_B² B = γ_c δ S                   [continuous]
    (8) R_B[n] = D²_h B[n] + (ω_B / Q_B) D⁻_h B[n] + ω_B² B[n] - γ_c δ S[n] = 0    [discrete audit]

Line (1) is the error, the energy of misalignment: it decays at its own rate, it is pushed by forces from inside and
outside, and it is pushed by the effective velocity of the system. Line (2) is coherence, the alignment index: it
lives in a double well with two homes at +1 and -1, it is pulled down by any rise in error, it leaks, and it is the
one line the governor touches, through the control u, which is never allowed beyond its authority. Line (3) is the
information channel that keeps the record of how far coherence has been from home. Line (4) is the effective
velocity, saturated so that it can never exceed the limiting speed c, and multiplied by the spinor phase. Lines (5)
and (6) are the potential of the coherence state and the flow it creates, downhill. Line (7) is the bath, the field
that every real system sits in, driven by the state. Line (8) is the bath written on the grid the computer actually
steps on: it is an audit of the numbers, not a second bath.

## The control law

    σ        = nearest_signed_basin(U₀)
    u_m      = sat(-f_U(x_m, t_m) + K_P (σ - U_m), ± U_AUTHORITY)
    x_(m+1)  = RK4_h(x_m; u_m),   u_m held across all four RK4 stages

The nearest signed basin is declared at Step 0, before the first microstep. The control cancels the natural drift
of coherence and adds a proportional pull to the declared home, then it is clipped at its authority. It is held
fixed through the four stages of each RK4 step. There is no post-step overwrite of the state and no projection onto
the basin. Whatever the engine reaches, it reaches by the flow of its own equations.

## The symbol chart

![Plate 18. The equation form and the symbol chart](plates/equation_chart.jpg)

| Symbol | Meaning |
|---|---|
| E | Error, the misalignment energy |
| U | Coherence, the alignment index |
| I_U | Information, the internal-coherence channel |
| S | Coherence state potential |
| B | Bath field |
| B' | Bath field time derivative |
| α | Feedback rate |
| β_int(t) | Internal forcing function |
| β_ext(t) | External forcing function |
| k | Coherence logistic damping gain |
| σ₁ | Coupling of error into the information channel |
| δ | Linear coherence coupling parameter |
| λ₀ | Saturation bias |
| λ₁ | Saturation gain |
| λ₂ | S-state coupling gain |
| U_t | Target coherence state |
| c | Limiting velocity |
| E_max | Per-trajectory error-rate normalization scale |
| α_s | S-potential quadratic coefficient |
| β_s | S-potential cubic coefficient |
| Φ(S) | Potential field function |
| F_state(S) | Canonical S-state flow |
| ω_B | Bath frequency |
| Q_B | Bath quality factor |
| γ_c | Bath coupling gain |

## The coupling architecture of Piece I

The closed feedback core is E, U and S: error drives coherence, coherence and the state drive the velocity, the
velocity drives error. The information channel I_U and the bath B with its derivative are driven response channels:
they listen to the core and record it, and the core does not depend on them. γ₁ is reserved for compatibility and is
inactive in the Piece I derivatives. The bath law uses ω_B² B, so ω_B carries the units of angular frequency.
Line (7) advances B and B' continuously by RK4. Line (8) evaluates the discrete residual with
D²_h B[n] = (B[n+1] - 2B[n] + B[n-1]) / h² and D⁻_h B[n] = (B[n] - B[n-1]) / h.

## The spinor closure

The spinor extension introduces the phase θ(t) = ω_B t and multiplies line (4) by χ(θ) = cos(θ/2). At 0 degrees the
factor is +1, at 360 degrees it is -1, and at 720 degrees it is +1 again. A full turn of the bath reverses the sign
of the velocity; only two full turns bring it home. The standard 20-step run evaluates the part of the phase it
reaches, and a dedicated evidence test checks the 0, 360 and 720 degree periodicity on its own.

## The signed basins

The canonical Monte Carlo sampler draws the starting coherence U(0) symmetrically on [-1, +1]. The nearest signed
basin at Step 0 is declared the target before the first microstep. That keeps the eight-line equation exactly as
written while making every governed run exercise capture into both +1 and -1. A separate dual-basin suite throws
runs across from one basin to the other under disturbance and watches them recover.

## Birth, conveyance and certification

Step 0 is the sampled state before integration. Step 1 is the first completed macro step. A run has at most 20
macro steps of 10 micro steps each, at a time step of 0.1. A step is in basin when U lies within 0.10 of +1 or -1.

- **Born in basin.** A run that starts inside a basin at Step 0 is born in basin for life. Step 0 counts as the
  first observation of its streak. It is confirmed conveyed after Steps 0 to 4 stay in the same basin. It is never
  called self-tuned, and it stays under the same regulation for all 20 macro steps.
- **Self-tuning.** A run that starts outside both basins is self-tuning applied from Step 1. The same nearest-basin
  law is active on every trajectory, born or not, over the whole 200-microstep horizon. The category never switches
  the regulation off.
- **CONVEY-5.** Five consecutive same-basin observations. The first is the conveyance entry step, the fifth is the
  confirmation step. The latest streak may start at Step 16 and confirm on Step 20.
- **CERT-10.** Ten consecutive same-basin observations. The latest streak may start at Step 11 and complete on
  Step 20. The code asserts both bounds before it runs and checks every emitted row against them.

Conveyance is an event, not an ending. No run may be both born in basin and self-tuned. Stability is judged on the
history, not on one snapshot.

## The Monte Carlo declaration

| Setting | Value |
|---|---|
| Initial U distribution | Uniform on [-1, +1], symmetric |
| Monte Carlo runs | 500 |
| Macro steps per run | 20 |
| Micro steps per macro step | 10 |
| Integration time step | 0.1 |
| Basin centers | +1 and -1 |
| Basin tolerance | 0.10 |
| Stability window | 5 |
| Conveyance cutoff step | 20 |

The full horizon is always executed. A run is classified as a failure if it crosses the divergence threshold at any
recorded state, or if it exhausts the horizon without CONVEY-5.

## The parameter sets

| Group | Parameter | Value or range |
|---|---|---|
| Core | α | 4.2 |
| Core | β_int | 0.0 to 1.0 |
| Core | β_ext | 0.0 to 1.0 |
| Core | E_max | 1.0 to 10.0, sampled once per trajectory |
| Core | k | 1.7 |
| Information and coupling | σ₁ | 0.38 |
| Information and coupling | δ | 0.01 to 1.0 |
| Information and coupling | γ₁ | 1.35, reserved, inactive in the derivatives |
| Information and coupling | γ_c | 1.0 |
| Saturation and phase | c | 0.5 to 5.0 |
| Saturation and phase | λ₀ | -2.0 to 2.0 |
| Saturation and phase | λ₁ | 0.1 to 3.0 |
| Saturation and phase | λ₂ | 0.0 to 2.0 |
| Saturation and phase | U_t | 0.5 |
| Saturation and phase | χ(t) | cos(ω_B t / 2) when the spinor closure is on |
| S-state potential | α_s | 0.05 to 0.25 |
| S-state potential | β_s | 0.05 to 0.25 |
| Bath | ω_B | 0.1 to 5.0 |
| Bath | Q_B | 0.5 to 10.0 |
| Noise and drift | D | 0.0 |
| Noise and drift | μ | 0.0 |

## The mechanism-bound reporting doctrine

Every table, grid, chart, scorecard, classification and conclusion the engine emits must be computed from what it
actually executed: the trajectory rows, the recorded state histories of E, U, I_U, S, B and B', the sampled
parameters, the RK4 derivative evaluations, the basin entry and dwell histories, the line (8) residuals, the solver
comparisons, the ablations, the disturbance and stress runs, the compute benchmark event records, and the enterprise
benchmark ledgers.

No decorative grade, inferred score, hand-assigned quality category or presentation-only number is allowed to stand
as an engine result. Prose may point to the exact source and the edge of the claim. It may not manufacture evidence,
put a grade where a measurement belongs, or present a grid the mechanism never ran as though it had. That doctrine
runs through every page of this book.

## Availability and the rights boundary

Time is of the essence. Omni-Compass is available from The Omni-Compass LLC for controlled technical evaluation,
research collaboration, pilot integration, strategic engagement and separately licensed commercial deployment. The
same rights boundary applies at every level of use: inspection, local execution, simulation, research,
benchmarking, observe-only, shadow mode, supervised control, bounded autopilot, hybrid control, direct-to-muscle
control, production, embedding, hosted service, productization, monetization, redistribution and derivative work.

Public access does not make Omni-Compass open source. Commercial use of any kind requires a separately executed
written license. The instrument is a license, not a sale and not a transfer of ownership. For planning only, the
introductory benchmark is 10% of independently verified and contractually accepted value captured; the base and the
amount are specific to each company, the terms are expected to rise as validation and adoption grow, and only a
signed agreement creates any obligation.
