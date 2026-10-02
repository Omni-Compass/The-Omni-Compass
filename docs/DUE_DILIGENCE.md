# Due Diligence

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Answers reference the Claims Register (C-numbers) and the Technical Manual.

## Engineering
**Does the mathematics hold?** Equations (1) to (8), Propositions 1 to 3 and their proofs are in Manual Chapters 2 and 3. The 500/500 CONVEY/CERT result is a property of the controller (Proposition 3), shown by counterfactuals: the controller aimed at the wrong basin also scores 500/500.
**Is Python the same as C++?** Yes (C1, C2). The verifier also builds a deliberately mutated C++ governor and confirms the parity test rejects it.
**Can every number be reproduced?** `python verify.py` rebuilds the C++, reruns parity, reruns the 100,000,000-decision soak and compares it with the recorded result, replays held-out scenarios and checks the pre-registered SHA-256 hashes (program fingerprints are additionally checked when the Python version matches the recorded one).

## Operations
**Better than what we run today?** Compared against a documented-behaviour reference model of Kubernetes autoscaling (HPA tolerance 0.1, 300 s scale-down stabilization, HPA targets 0.5 to 0.8; simplified Cluster Autoscaler with 10-minute unneeded time, 0.5 utilization threshold, 10-minute delay after scale-up): C8 to C12, including where Omni-Compass is worse. The reference model is not the upstream controllers (C12b); running the upstream controllers against the same scenarios is the next baseline step.
**On real traffic?** Not yet. Results use a synthetic stack model. Replay of published production traces and the pilot protocol are the next evidence steps (C14).
**What happens when it is wrong?** Observe mode changes nothing (C6). The kill switch returns control to the native managers at the next interval (omni_kill arm). The shield blocks actions that violate I1 to I5 (C7).
**Will it wear hardware?** Machine start/stop cycles, power-cap travel and thermal travel are measured for every arm (C12, Manual Chapter 8).

## Security
**What authority does it hold?** Capacity, replicas, power caps, rollback authorization and routing, only in AUTOPILOT, only through the shield.
**Can it expand capacity during a security block?** No: invariant I1 is enforced before execution.
**Does it replace encryption, identity or policy engines?** No. Those components are retained (fleet model, security role).

## Finance
**What does it save?** Energy per run versus current autoscaling (C8). Fleet-scale figures are modeled (C13); the governance saving comes from reduced idle and padded capacity, not from removing the decision components' own consumption.
**What does it cost to run?** C5.

## Adoption
**How is it introduced without risk?** Observe, then shadow on production telemetry, then one control loop at a time under the kill switch (docs/PILOT_PROTOCOL.md).

## Referees
**Was it tuned on the test data?** No. Law, shield and baselines were frozen and fingerprinted before the held-out seeds 346410161 and 360555127 (results/PREREGISTRATION.json).
**Where does it fail?** Backlog violations against current autoscaling (C11); the engine-dynamics ablation (Manual Chapter 8); open obligations (Manual Chapter 10).
