# Preregistration: the bowl law on real Kubernetes (set 26)

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Written and committed before the run. The run's commit is the one that carries this file; nothing in the law, the
harness or this rule changes after it starts.

## What is run

Workflow `benchmark-reps` on `main`, 10 repetitions. Each repetition runs three arms back to back on the same runner,
each on a fresh six-worker kind cluster, in an order rotated by repetition (`scripts/kind_paired.sh`):

| Arm | What governs |
|---|---|
| native | Kubernetes alone (HPA at target 50, scheduler); Omni-Compass not started |
| omni | Omni-Compass on top with the engine's allocation law (`--law governor`, the law of sets 22 to 25) |
| bowl | Omni-Compass on top with the bowl law (`--law bowl`, `omni_controller/controller.py`) |

Load: fixed rate (`loadgen=open`), the same work in every arm. 900 measured seconds per arm. SLO 500 ms at the 95th
percentile. Every Omni arm runs the six-state engine on every decision, the nervous system's authority and release
gate, the shield, the compass, and ends with the kill switch, which must return the HPA target, its replica range,
the pods' CPU limits and every worker to native, with no record left (`scripts/kind_bench.sh`).

## The bowl law in the live controller

The service position is the 95th-percentile response time over the SLO (0 calm, 1 the line); a blind probe or a pod
waiting for a place reads as past the wall. The force is `A tanh((K_P (p - 0.5) + K_D v) / A)` with K_D for critical
damping times the realm push factor 3, the same law and gains as on every realm muscle (`realms/bowl_arm.py`):
up gain 0.10, down gain 0.02, release threshold -0.2. Two levers:

1. **HPA target**, cover from 60% of the operator's target to the operator's own: the up force lowers it (more pods),
   the down force returns it toward the operator's. It is never tighter than native.
2. **Node pool**: past the 0.95 wall one machine more at once; one machine back only while the force is below -0.2,
   the position is below the center, and the nervous system's release gate is open.

## Outcomes and the rule

Primary: **worker nodes in service** (mean) and **95th-percentile response time**, each arm against native, paired
over the 10 repetitions with a t-based 95% interval (`tools/live_reps.py`).

Band first: the bowl arm is a win only if its p95 is not worse than native's (the upper end of the 95% interval of the
paired difference at or under 0) **and** failed requests are not higher. If that holds and machines in service fall
with an interval wholly below 0, the label is **better on machines within the band**. If machines fall but the band
condition fails, the label is **tradeoff**. Otherwise **not established**.

Secondary, reported, not used for the label: p99, mean response time, HPA replicas, pods started, pod start wait, CPU
including Omni-Compass's own, the declared energy models. The omni arm is reported against native and against the
bowl arm by the same rule. A run that fails its own checks (kill switch, controller stopped early, missing permission)
is marked invalid and left out, never silently counted.

Evidence class **L**: real Kubernetes software on kind. Energy on kind is a declared model, not a meter.
