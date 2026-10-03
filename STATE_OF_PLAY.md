# Omni-Compass: state of play (read this first)

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](LICENSE).

Current facts only. Earlier states, failures and chronology are kept whole in `docs/HISTORY.md`. The release this page
describes is identified by `RELEASE_MANIFEST.json` (commit, fingerprints of the engine, the C++ twins, the GPU protocol,
the live evidence and the verification receipt), which `verify.py` checks against the files.

**Rerun everything:** `pip install -r requirements.txt && python verify.py` ends with `VERIFICATION: PASS`.

## In one paragraph

Omni-Compass is a supervisory governor that sits on top of Kubernetes and hardware. On a real Kubernetes control plane
it measurably makes services answer faster, on about a third fewer machines, with a clean kill switch. On kind every
machine stays powered, so energy there is a declared model. On a real card (NVIDIA A10 on Lambda, the card's own meter,
10 paired runs, `results/gpu/run-20261002T082232Z/GPU_REPS.md`) the first governor saved energy (+3.6% work per energy,
proven) but made the slowest answers 58.5% slower, so its label by rule is energy improvement with service tradeoff.
The cause was the governor's wiring, corrected in GPU amendments 6 and 7; the corrected governor has not yet run on a
card, so no real-hardware result inside the band exists yet. In the models, the bowl law on every muscle of the six organisms gives +0.20% to +0.30% work
per energy at every size and run count completed, but it spends more time over the service line than native in every
cell, so the band-first rule is not yet held. Closing that is the open work on the engine.

## Measured on real systems: the newest set, Omni-Compass against Kubernetes as it runs today

**Set 24 (2026-10-02, commit `c908054`) repeats it again: machines in service −31.6%, p95 −60.1%, p99 −64.1%, HPA
replicas −38.6%, 0 failed requests, total CPU including Omni-Compass's own −1.8% (not significant)**
(`results/live/LIVE_REPS_24.md`). Set 23 before it: p95 −62%, replicas −37%, pod starts −64%, 0 failed requests, no
energy or total-CPU difference (`results/live/LIVE_REPS_23.md`). The set-22 table below stands as first measured.

Set 22 (`results/live/LIVE_REPS_22.md`): 10 paired repetitions on real Kubernetes (kind), each pair on one machine,
Kubernetes with its autoscaler alone against the same Kubernetes with Omni-Compass on top. The load is sent at a fixed
rate, so both arms were given **the same work**.

| Result | Kubernetes alone | With Omni-Compass | Change (95% interval) |
|---|---:|---:|---|
| **Energy, parked machines still on at idle power** (declared model, no meter) | 160.3 Wh | 160.1 Wh | **−0.1%, no difference** |
| **Response time, 95th percentile** | 407.9 ms | 158.8 ms | **−61%** (proven) |
| Response time, 99th percentile | 639.4 ms | 245.1 ms | −62% (proven) |
| Response time, mean | 179.9 ms | 98.4 ms | −45% (proven) |
| Failed requests | 0 | 0 | equal |
| Pods waiting to start, pod-minutes | 0.265 | 0.025 | −91% (proven) |
| Replicas, mean | 8.93 | 6.91 | −23% (proven) |
| Machines in service, mean (all stayed powered) | 6 | 4.14 | −31% (proven) |
| CPU used by the service | 1.036 cores | 0.957 cores | −7.6% (proven) |
| Omni's own CPU (its controller and every command it ran) | 0 | 0.070 cores | +0.070 (proven) |
| **CPU used, service and Omni together** | 1.036 cores | 1.026 cores | **−0.9%, no difference** |

- **Same work, much faster answers**, with no failed requests and far less waiting.
- **No energy saving is shown on kind.** Every machine stays powered; energy is a declared model, and counted at the
  idle power a parked machine really draws it is unchanged.
- **No CPU saving once Omni's own cost is counted.** The service used 7.6% less CPU; the controller spent almost all
  of it. Cutting the controller's cost is the next improvement.
- The kill switch restored every setting in every run.

## Kubernetes sets 25 and 26 (2026-10-02, 10 paired repetitions each, equal work)

| Run | Machines in service | p95 | Failed | Total CPU incl. Omni's own | Receipt |
|---|---:|---:|---:|---:|---|
| Set 25, the engine's allocation law | **−32.3%** | **−57.3%** | 0 / 0 | −0.6% (not significant) | `results/live/LIVE_REPS_25.md` |
| Set 26, the engine's allocation law | **−35.8%** | **−55.4%** | 0 / 0 | −1.5% (not significant) | `results/live/LIVE_REPS_26.md` |
| Set 26, **the bowl law in the live controller** | **−17.2%** | **−64.8%** | 0 / 0 | +1.0% (not significant) | same; label by the preregistered rule: **better on machines within the band** |
| Set 27, the engine's allocation law | **−36.6%** | **−53.1%** | 0 / 0 | −0.0% (not significant) | `results/live/LIVE_REPS_27.md` |
| Set 27, **the bowl law aligned with the GPU governor** | **−15.9%** | **−65.5%** | 0 / 0 | +0.2% (not significant) | same; label by the preregistered rule: **better on machines within the band** |

Set 27 (running): the bowl in the live controller reads the service as the corrected GPU bowl does (mean response time,
center 0.4), against native and the allocation law (`docs/K8S_BOWL_PREREGISTRATION.md`).

## Measured on a real GPU: the card's own meter (evidence class P)

**First confirmation, NVIDIA A10 on Lambda, 2026-10-02** (`results/gpu/run-20261002T082232Z/GPU_REPS.md`, 10 paired
repetitions × native / watch / Omni, 600 s each, frozen at commit `c908054`, checksums verified). Wire check 7 of 7;
2,144 writes, none refused, every one read back, every arm ended at the start limit; watch equal to native.

| Gauge | Native | Omni | Change (95% interval) |
|---|---:|---:|---|
| **Work per energy** (requests per kJ) | 50.79 | 52.62 | **+3.6% (+2.7% to +4.5%), proven** |
| GPU energy | 69,180 J | 66,790 J | −3.5%, proven |
| Requests served / not served | 3,514 / 0 | 3,514 / 0 | equal |
| **Response time, 95th percentile** | 510 ms | 809 ms | **+58.5%, worse, proven** |

**Result, by rule: ENERGY IMPROVEMENT WITH SERVICE TRADEOFF** (the p95 guardrail of +10% failed). The six organisms
with the same card inside (`results/hil/run-20261002T082232Z/HIL.md`, 3 repetitions each): the card's work per energy
+1.6% to +2.8% in every organism, the same requests, its p95 500 to about 600-935 ms. The cause, from the card's own
samples, was wiring in the governor (amendment 6 of `docs/GPU_PREREGISTRATION.md`): busy bursts served at 736-768 MHz
against 861-889 MHz on its own. Corrected (amendments 6 and 7); the corrected governor has not yet run on a card.

## Simulated (models: they show the mechanism, not a measurement)

| Result | Where |
|---|---|
| GPU governor with share floor and busy gate (one wire, the power limit), MLPerf-calibrated card: +5.1% and +1.3% work per kJ, p95 within +10% | `results/gpu/sim/after` |
| **Two-wire GPU card under the bowl law, corrected governor** (amendments 6-7), 10 seeds and 10 fresh seeds, geometric means: **service** profile work per energy **+6.9% / +3.8%**, energy −6.4% / −3.7%, p95 **−5.9% / −2.3%** (faster), time over the line −0.03 / −0.04 pp; **batch** profile +8.1% / +4.2%, p95 +7.0% / −2.3%; the one-wire governor +0.1%; both wires restored every seed | `results/sim/gpu_two_wire/RESULT.md`, `fresh/` |
| **The six organisms** (Compute 345, Physics 262, Energy 282, Distribution 337, the four stacked 1,226, the whole tower 656), native against the bowl law on every muscle, 1,000 paired runs at 1× and at 10× size: work per energy +0.20% to +0.30%, energy −0.21% to −0.32%, work −0.01% to −0.02%, time over the service line **+0.19 to +0.27 pp in every cell (band first not held)**, every knob handed back. 100× and 1,000× are running | `results/scale/GRID.md` |
| Speed lock (speed won elsewhere spent on GPU watts) | `results/gpu/sim/pipeline/` |
| CPU and GPU on one conserved power budget: +1.4% to +5.7% work served against a fixed cap, never over the budget | `results/hardware/NODE_EXCHANGE_*.json`, `docs/CONVEYANCE_LAW.md` |
| GPU groups sharing a site budget: 0 minutes over the budget | `results/hardware/SITE_EXCHANGE_HELDOUT_*.json` |
| Platform leagues, faults, PlanetLab traces, stack benchmark | `tuning/`, `results/protocol/`, `results/` (see `docs/BENCHMARK_REPORT.md`) |
| **The 656-muscle tower as organisms**, round 3 (preregistered, 10 seeds; every realm carries the shared spine; Omni as the shipped controller commands): the whole tower native against one governor on top, work per energy **+0.1%, SUPERIOR WITHIN GUARDRAILS**; inside the realms the spine costs service: Energy +0.2% with +1.9 pp violations (tradeoff), Compute 0.0% (+2.1 pp, not established), Distribution −0.1% and Physics −0.7% (**WORSE**). Rounds 1 and 2 kept, superseded | `results/realms/REALMS.md`, `docs/REALM_MUSCLES.md` |

## Verified in code

| Property | Where |
|---|---|
| The canonical engine is `symmetric_verified`; the printed chart is a named variant, not benchmarked | `docs/CANONICAL_ENGINE.md` |
| Nine laws twinned in C++20 and proven equal to the Python; sealed by fingerprint | `results/SEAL.json`, `tools/seal.py` |
| The conveyance law conserves its budget and converges (proof and 20,000 random systems) | `docs/CONVEYANCE_LAW.md`, `tests/test_conveyance.py` |
| Safety shield: 2,000,000 adversarial cases, 0 violations; C++ engine: 100,000,000 decisions, no failures | `tests/test_shield_properties.py`, `results/SOAK.json` |

## Open

1. **Band first.** In every organism and every size the bowl law raises the time over the service line by about 0.2
   points. The rule is no win unless that is at or under native's. This is the first thing to fix in the law.
2. **The first real-hardware run:** `sudo bash scripts/gpu_rented_run.sh` on a rented NVIDIA machine (smoke, then the
   10 preregistered repetitions, `docs/GPU_RUN_GUIDE.md`), or the gpu-bench workflow on GitHub's GPU runner. Then a
   second machine of the same type, then another GPU type. Status 2026-10-02: the rented-card run above is under way. GitHub's GPU runner has never been
   assigned to a job (every run waited in the queue; the repository is public, so the ordinary runners are free while a
   GPU runner is always billed, and the account has an Actions billing notice). The envelope rule is preregistered
   (amendment 3).
3. **Work per energy on kind:** count requests served, or run an open-loop load at a fixed rate, so work per energy can
   be stated instead of estimated (set 22, `LOADGEN=open`).
4. **CPU and GPU on one power budget on hardware:** the law is simulated; the live exchange is not wired.
5. **A global stability proof** of the forced six-state system (`docs/FORMAL_STATUS.md`).
6. **The principal embodiment for filings** (`docs/CANONICAL_ENGINE.md`, section 5): a decision for the company.

## Where things are

| Path | What it is |
|---|---|
| `docs/INTEGRATION_MANUAL.md` | the manual in the box: wiring it in yourself, stack by stack |
| `docs/METRICS_CATALOG.md` | every gauge, and whether it is measured or modelled |
| `docs/COMPARISON.md` | against Kubernetes, OpenShift, Turbonomic, Borg, Twine and others |
| `docs/CANONICAL_ENGINE.md` | the one engine the software runs |
| `omnicompass/`, `cpp/` | the engine and its laws; the C++20 twins |
| `omni_controller/` | the Kubernetes controller, the GPU governor, the muscles |
| `results/live/` | every live run, including failed and withdrawn ones |
| `docs/HISTORY.md` | earlier states of play |
