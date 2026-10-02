# My engine, line by line: the source against what runs in your cluster

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

**The source.** `docs/handoff/mathematics/omni_compass_engine_source_c527df2d.py` (SHA-256 c527df2d…, 31,348 lines).
Every mechanism below is named by its function there, followed by where it runs live and how it is checked on every
`python verify.py`.

| Mechanism | In the source | Where it runs | Checked by | Status |
|---|---|---|---|---|
| Six states E, U, I_U, S, B, Ḃ and equations (1)–(7) | `oc_derivatives`, `rk4_step` | `omnicompass/core.py` | `tests/test_core_parity.py`: 20,000 random states, max difference ≤ 1e-12 | exact |
| Spinor closure, 720°: drive × cos(½ ω_B t) | `v_eff`, `spinor_closure_factor` | `core.v_eff` | same parity test | exact |
| Axle rest S* from equation (6) | `stable_S_equilibrium` | `omnicompass/storage.py`, `compass.axle` | parity; `tests/test_compass.py` | exact |
| Double well W(U), basins ±1 | `W_potential`, `W_gradient_flow` | `core.derivatives` | parity | exact |
| Regulation u = −f_U + K_P(σ − U), clipped at the authority | `hybrid_microstep_operator` | `core.control_command`; the governor's push | parity; 500 frozen trajectories (`fixtures/`), 0 mismatches | exact |
| Basin lock, conveyance, certification | `run_monte_carlo`, `macro_step` | `core.simulate` | 500 frozen trajectories, 0 mismatches | exact |
| Composite storage V = V_U + V_W + V_E + V_S + V_I + V_B, the ledger that closes the circle | `composite_practical_lyapunov_value`, `bath_lyapunov_matrix`, weights | `omnicompass/storage.py`, read by the compass every decision | parity on 5,000 states (≤ 1e-13); descends 648 → 8 over 60 regulated steps with no rise | exact |
| Human switch: a file or a variable stops every command | `_oc_runtime_stop_requested` | `--kill-file`, restore of every lever | `tests/test_failsafe.py`, `tests/test_muscles.py`, every live run's switch drill | exact |
| Cap doctrine C1: only a ceiling *above* the reference is admissible; a lower one buys energy by slowing work | `_ci_omni_decision`, certificate C1–C4 | `muscles.convey`: CPU limit never below the operator's, idle CPU conveyed to the work | `tests/test_convey.py` | exact |
| Sleep only in a certified empty interval | `_ci_omni_decision`, sleep channel | `scripts/kind_nodepool.sh`: a machine idles only once its work has left | `tests/test_active_nodes.py`, `tests/test_convey.py` | exact |
| Reference Kubernetes HPA rule | `oc_hpa_desired_replicas` | `cpp/` HPA, pod reflex | `tests/test_cpp_hpa_parity.py` | exact |

## Where my live wiring reads the engine differently from the source's own embodiment

**Evolution between decisions.** The source's compute embodiment advances the assimilated state *with* regulation
locked on basin +1. My live governor advances it with u = 0 and reads the regulation command separately, as the push
that gates every machine release.

- Both use the same equations.
- The difference is whether the regulation is applied to the state or only read from it.
- The pre-registered, frozen results were measured with u = 0. I keep that setting, and I report the difference here
  rather than change a frozen law mid-measurement.
