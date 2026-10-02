# The two-way nervous system (live controller)

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

**Source.** Manuscript Appendix J: "Nervous system. The signal layer: sensing interfaces, unit integrity, timing
coherence, delay and dropout handling, and feedback interpretation. … The brain cannot compensate for corrupted
signals." Section 5.3: the engine "projects forward state trajectories … and detects destabilization pressure before
divergence."

**The gap.** Before this change, the live controller fed the engine's `stale` (signal dropout) and `drift_ratio`
(actuation mismatch) channels with a constant 0. So the upward path could not report a blind sense, and the downward
path never learned whether its orders landed.

## Upward: afferent integrity (senses to engine)
**Every declared sense reports whether it is live.**
- **Latency.** Blind when its newest sample is older than two windows by the wall clock, or when the window holds no
  successful request.
  - A hung probe freezes its file; its last clean window must never be read as the present.
  - Failed requests inside a live window become latency pressure (the failed share), so a failure is never read as
    silence.
- **Power.** Blind when its command returns no number.

**How blindness is used.**
- The blind share enters the engine as `stale`. It raises E, lowers U and feeds the external bath (equations 1-3 via
  `assimilate`).
- The nervous system grants no contraction on a blind sense, to any organ, and admits no held batch work.
- Expansion and batch pause (the protective directions) stay allowed.

## Downward and back: efferent feedback (proprioception)
**Every command is recorded.**
- The node count commanded.
- The HPA targets written.

**At the next decision the observed state is read back.** For each organ, `drift = |observed - commanded| /
commanded`.
- The largest drift enters the engine as `drift_ratio`. It raises E and I_U, lowers U and feeds B (equations 1-3).
- The node organ may not be given a new release while its last command did not land. For example, a drain refused
  by the PodDisruptionBudget leaves the node in service, and the next decision sees it.

## Sideways: attribution (organ to organ)
**The machine organ has its own engine view**, fed with machine-attributable pressure only (pods waiting for a place).

**It releases a machine only when all of these hold:**
- pods are not scaling up and latency is not breached;
- nothing is pending;
- after the release the remaining machines stay at or below the engine's rho;
- its own calm, stress and security gates grant contraction;
- every sense is live;
- its last command landed.

## Tests (all in `verify.py`)
| Test | What it checks |
|---|---|
| `tests/test_two_way.py` | blind senses (about 75,000 random states), frozen-probe detection, failures read as pressure, release refused while blind or after an order that did not land |
| `tests/test_node_release_gate.py` | the release gate, over 200,000 states |
| `tests/test_nervous_system.py` | the original invariants N1-N6, over 300,000 states |

Every live decision records the senses, their ages, the proprioceptive drift and the gate's reason in the audit, and
the benchmark prints them in the job log.
