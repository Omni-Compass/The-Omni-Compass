# Evidence ledger

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Every material statement in the technical package gets exactly one primary evidence class. A statement never
borrows a stronger class from the one printed beside it.

| Class | Meaning | Layer |
|---|---|---|
| **T** | formally proved theorem, under stated assumptions | L1 mathematical mechanism |
| **V** | finite computational verification: exact over a declared finite set, never a theorem beyond it | L1 |
| **S** | simulation / model result | L2 modelled systems |
| **L** | live observation of external software (a real Kubernetes API, a real process) | L3 external software |
| **P** | independent physical measurement (a meter Omni does not read or control) | L4 physical plant |
| **O** | open: not established | — |

No layer stands in for another: a theorem is not a physical validation, a Monte Carlo result is not a theorem, and a
model's energy is not a meter's.

Mechanism identity for every row: `results/MECHANISM_IDENTITY.json`. Canonical engine `symmetric_verified`, mechanism
id `29d9808dfb8f…`; the printed configuration `printed_eight_line`, id `cd333dc166fb…`, is a named alternative
(Option A of the directive: one canonical, one alternative embodiment; no equivalence is claimed).

## Layer 1: the mechanism

| Class | Statement | Where |
|---|---|---|
| T | Unsaturated, the U-channel error obeys de/dt = −KP e; V = e²/2 has dV/dt = −KP e² < 0 for e ≠ 0 (inside Omega_unsat only). | `docs/TRACKING_THEOREM.md` Thm 1 |
| T | With the U drift bounded by F_bar < u_max, V decreases wherever e ≠ 0, saturated or not; e never changes sign; saturated stretches end in bounded time (continuous time). | Thm 2 |
| T | On the declared parameter box, F_bar = 16.86 < 25, so Thm 2 holds over the whole box in continuous time. | Thm 2 |
| T | The sampled controller (u held through each RK4 step) satisfies e_(k+1) = 0.88 e_k + d_k, hence abs(e_k) <= 0.88^k abs(e_0) + epsilon_h (1 − 0.88^k)/0.12. | Thm 3 |
| V | epsilon_h = 0.00378 over every micro step of the 500 frozen fixtures (nearest target); ultimate bound 0.0315 < BASIN_TOL 0.10. Wrong target: 0.0243, bound 0.20 (wider than the basin). | `results/TRACKING_BOUNDS.json` |
| V | The discrete execution dithers inside that band: abs(e) grew on 27 061 of 100 000 micro steps; e changed sign 747 times. The continuous monotone decay is not inherited. | same |
| V | Saturated micro steps: 0 of 100 000 (nearest target), 5 of 100 000 (wrong target). | same |
| T | The admissible box A (E interval, abs(U − sigma) <= abs(U0 − sigma), S between S0 and S_plus) is forward invariant in continuous time. | Thm 4 |
| V | Discrete invariance of A: 0 failures over 100 000 micro steps of the frozen fixtures, both targets. | `results/TRACKING_BOUNDS.json` |
| O | Discrete invariance and epsilon_h proved over the whole box (interval arithmetic). | — |
| O | Global stability of the forced six-state system. | `docs/FORMAL_STATUS.md` |
| V | 500 / 500 frozen fixtures satisfy CONVEY-5 and CERT-10 (dwell predicates, not external certification). | `results/core_evidence.json` |
| V | Frozen 500-fixture comparison: symmetric_verified final error 7.48e-5, integrated abs(u) 0.878, peak 13.93; printed_eight_line 5.13e-6, 11.79, 18.87. Both executable; not interchangeable. | `results/MECHANISM_IDENTITY.json` |
| V | Python and C++ produce identical results (engine, governor, shield, HPA law, conveyance, GPU rules); twins sealed. | `verify.py`, `results/SEAL.json` |

## Layer 2: models and simulations

| Class | Statement | Where |
|---|---|---|
| S | Synthetic stack: energy for Omni over the Kubernetes reference 168.9 → 121.7 kWh per run (documented-behaviour reference, not upstream controllers). | `docs/CLAIMS_REGISTER.md` C8 |
| S | Fleet harness, recorded PlanetLab shapes: −40.6% energy vs HPA+CA, −21.7% vs Karpenter-lite (omni_fleet). | C17 |
| S | Single GPU physics model: the engine alone would save 10.6–13.6% work per kJ on card A but breaks the p95 guardrail by 15–28%; with the frozen guards, about +1 to +5% inside it. | `results/gpu/sim/FINDINGS.md` |
| S | Node exchange (CPU and GPU on one budget): +1.4 to +5.7% work against the separate budgets, never over budget. | `results/hardware/NODE_EXCHANGE_*.json` |
| S | Six organisms (345, 262, 282, 337, the four stacked 1,226, the whole tower 656), the bowl law on every muscle against each organism's own controllers, 1,000 paired runs at 1× and 10× size: work per energy +0.20% to +0.30%, energy −0.21% to −0.32%; every knob handed back. | `results/scale/GRID.md` |
| S | Two-wire GPU card, corrected governor (amendments 6-7), geometric means over 10 seeds and 10 fresh seeds: service profile work per energy +6.9% / +3.8%, p95 −5.9% / −2.3%; batch +8.1% / +4.2%; the one-wire governor +0.1%. | `results/sim/gpu_two_wire/RESULT.md` |
| S | Realm harness round 3 (every realm carries the shared spine), preregistered, seeds 3000-3009: the whole 656-muscle tower native against one governor on top, work per energy +0.1% (+0.1 to +0.1), violations +0.5 pp, SUPERIOR WITHIN GUARDRAILS. Realms: Energy +0.2% with +1.9 pp violations (tradeoff); Compute 0.0% with +2.1 pp (not established); Distribution −0.1% (worse); Physics −0.7% (worse). Rounds 1 and 2 kept, superseded. | `results/realms/REALMS.md` |
| S | Stacked organism (round 4, seeds 4000-4009): the four realm organisms on one clock, 1,226 muscles with every duplicate; stacked native equals the four realms alone on every seed. One governor over the stack: energy −0.14%, work per energy +0.02%, violations +1.4 pp, ENERGY IMPROVEMENT WITH SERVICE TRADEOFF; four separate governors about the same (+0.04%); one governor against four separate: −0.02% (WORSE, by a hair). | `results/realms/stack/STACK.md` |

## Layer 3: live external software

| Class | Statement | Where |
|---|---|---|
| P | First real-GPU confirmation, NVIDIA A10 (Lambda), 10 paired repetitions, the card's own meter: work per energy +3.6% (+2.7 to +4.5, proven), GPU energy −3.5%, same requests, none lost; wire check 7 of 7, every write read back, every arm restored. | `results/gpu/run-20261002T082232Z/GPU_REPS.md` |
| L | Set 24 (2026-10-02, commit `c908054`), real Kubernetes (kind), 10 paired repetitions: machines in service −31.6% (proven), p95 response time −60.1% (proven), p99 −64.1% (proven), HPA replicas −38.6% (proven), 0 failed requests on both; total CPU including Omni's own −1.8% (not proven); energy with every machine powered −0.3% (declared model). | `results/live/LIVE_REPS_24.md` |
| L | Set 23 (set 22 repeated on the current code, 2026-10-02), real Kubernetes (kind), 10 paired repetitions, equal work: p95 response time −62% (proven), replicas −37% (proven), pods started −64% (proven), 0 failed requests; total CPU with Omni's own −1.0% and modelled energy −0.2% (no difference). | `results/live/LIVE_REPS_23.md` |
| L | Set 22, real Kubernetes (kind), 10 paired repetitions, equal work (fixed-rate load): p95 response time −61% (proven), replicas −23% (proven), pending pod-minutes −91% (proven), 0 failed requests. | `results/live/LIVE_REPS_22.md` |
| L | Set 21, real Kubernetes (kind), 10 paired repetitions: p95 response time −37% (proven), replicas −12% (proven), 0 failed requests. | `results/live/LIVE_REPS_21.md` |
| L | Omni patched a real Kubernetes API in place (no restart); the kill switch restored every setting in every run; watch mode wrote nothing. | same, `results/live/` |
| S | Set 21 energy is a declared model, not a meter: +1.8% worse with parked machines at idle power. | same (energy table) |

## Layer 4: independent physical measurement

| Class | Statement | Where |
|---|---|---|
| O | Omni changes successful work per measured joule on a GPU. The bench is built with three receipts (governor, actuator, outcome), the three contrasts (observation, authority, total), and result labels by rule; it has **not** been run on a card. | `scripts/gpu_paired.sh`, `docs/GPU_PREREGISTRATION.md` |
| O | Production data-centre energy effect. | — |
| O | Whether the power limit is the right actuator for LLM serving. Published measurements (arXiv 2605.11999, H200) find memory-bound decode draws 137–300 W of 700 W, so no power cap binds; clock scaling is what saves energy there (arXiv 2501.08219, GreenLLM 2508.16449). The pinned bench workload is compute-bound, where the cap does bind: a result on it does not transfer to LLM decode. | external literature |
| O | Wall-plug (whole-machine) energy effect; CPU package and DRAM (RAPL) effect. | — |
| — | What the GPU bench will attribute: per write, joules and requests against native, and which rule decided it (engine, floor, gate, reflex, heat, speed lock). | `tools/gpu_reps.py` |

## Negative evidence, kept

Nothing here is deleted when a later result looks better.

| Class | Statement | Where |
|---|---|---|
| P | Same run: p95 response time **+58.5% worse** (510 to 809 ms), mean +48%; label by rule ENERGY IMPROVEMENT WITH SERVICE TRADEOFF. Cause: governor wiring (busy bursts served below the card's own clock); corrected in amendments 6-7, not yet re-run on a card. | `results/gpu/run-20261002T082232Z/GPU_REPS.md`, `docs/GPU_PREREGISTRATION.md` |
| S | Two-wire GPU card, batch profile: p95 +7.0% (−4.8 to +20.3) on the tuning seeds; the governor before amendment 6 gave p95 +32.9% and +37.1%. | `results/sim/gpu_two_wire/RESULT.md`, history in git |
| S | Six organisms, same runs: time over the service line **+0.19 to +0.27 pp worse in every cell**; band first is not held anywhere. | `results/scale/GRID.md` |
| L | Set 21: modelled energy 1.8% **worse** with every machine powered (the only honest energy row on kind). | `results/live/LIVE_REPS_21.md` |
| S | Realm harness round 1 (superseded, kept): all five organisms **worse** (whole tower −0.1%). Its Omni layer did not follow the shipped controller (no contraction authority or SLO reflex, the stack law in place of the HPA, request traffic paused, a site budget under native draw). | `results/realms/round1/` |
| S | Realm harness round 2: the Physics / Robotics / Autonomous organism **worse** (−1.9%, violations +2.9 pp); the Compute organism's +2.5% costs +2.9 pp of service violations; 68 single muscles worse, mostly batch pacing and cooling setpoints under the live cooling law. | `results/realms/REALMS.md` |
| L | Set 22, equal work: no CPU saving once Omni's own CPU is counted (service −7.6%, controller +0.070 cores, together −0.9%, not proven); modelled energy unchanged (−0.1%). | `results/live/LIVE_REPS_22.md` |
| L | Set 20: the "same work" reading was wrong; requests were +35%. | `results/live/LIVE_REPS_20.md` addendum |
| L | Sets 1–2: machine savings **withdrawn** — a broken probe had blinded the latency sense. | `results/live/LIVE_REPS_PROBE_DEFECT.md` |
| L | Set 3 with a working probe: Omni kept all 6 machines; no significant difference except more waiting pods. | `docs/HISTORY.md` |
| L | Set 21: pending pod-minutes +238% (not proven); pod starts +37% (not proven). | `results/live/LIVE_REPS_21.md` |
| S | GPU and batch: energy 1–2% **worse**, power and heat margins 1–4% worse than tight packers (AKS/Karpenter, CAST AI, Spot). | `docs/HISTORY.md` |
| S | Machine round trips 1.1 → 1.7 per run (**worse**) in 6 of 8 seed-target combinations. | C12 |
| S | Power-protect mode: backlog violations 2.5% → 6.7% (**worse**). | C12p |
| S | Park strategy on PlanetLab shapes: energy +1.3% vs HPA+CA, +33.6% vs Karpenter-lite (**worse**). | C17 |
| S | Typical response time about 20% slower than every platform in the web and four-cluster simulations. | `docs/HISTORY.md` |
| S | GPU model: the engine without its guards breaks the p95 guardrail. | `results/gpu/sim/FINDINGS.md` |
| S | The compass-stroke GPU variant was tried and not adopted. | same |
| S | Right-sizing against VPA: p95 +15%, memory (OOM) kills +531%. | `docs/BENCHMARK_REPORT.md` |
| — | Reported in the external master-build report (not reproducible from this repository): on fresh scenarios Karpenter+VPA sometimes used less modelled energy than Omni, while Omni had lower churn and fewer request-induced evictions. Kept here so it is not lost; to be re-run here before it is cited. | external |
