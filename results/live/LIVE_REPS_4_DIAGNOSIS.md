# Live set 4 (GitHub Actions run 36291308356, commit cdc8cd9): why Omni-Compass held all six machines

All 15 runs succeeded. The aggregate job failed before it got a runner (no steps ran), so this set has no aggregate
table. Its purpose was the decision trail, printed in each job log.

**Decision trail, Omni-on-top run 1** (job 108541805932), 15 decisions:

```
6 -> 6 | p95 None  | clean False | calm 0.376 | contract False | queue 0.0
6 -> 6 | p95 421.8 | clean False | calm 0.568 | contract False | queue 0.0
6 -> 6 | p95 427.9 | clean True  | calm 0.627 | contract False | queue 0.0
6 -> 6 | p95 695.3 | clean False | calm 0.451 | contract False | queue 0.391   <- load step
6 -> 6 | p95 508.3 | clean False | calm 0.582 | contract False | queue 0.017
6 -> 6 | p95 517.4 | clean False | calm 0.617 | contract False | queue 0.035
6 -> 6 | p95 579.6 | clean False | calm 0.558 | contract False | queue 0.159
6 -> 6 | p95 500.2 | clean False | calm 0.618 | contract False | queue 0.0
6 -> 6 | p95 344.8 | clean False | calm 0.638 | contract False | queue 0.0
6 -> 6 | p95 390.8 | clean False | calm 0.642 | contract False | queue 0.0
6 -> 6 | p95 407.6 | clean True  | calm 0.637 | contract False | queue 0.0
6 -> 6 | p95 707.4 | clean False | calm 0.449 | contract False | queue 0.415   <- load step
6 -> 6 | p95 523.1 | clean False | calm 0.574 | contract False | queue 0.046
6 -> 6 | p95 356.5 | clean False | calm 0.639 | contract False | queue 0.0
6 -> 6 | p95 383.6 | clean False | calm 0.654 | contract False | queue 0.0
```

## Two gates held the machines
**1. SLO clean.** It was false in 13 of 15 decisions.
- p95 spiked to 695-707 ms at each load-generator step, while php-apache saturated until the HPA added pods.
- Each breach blocks release for the next 3 decisions.

**2. Calm.** It never passed 0.654, and the node organ's threshold is 0.7.
- An offline replay decomposes calm and finds it capped by basin health: h = (U - 0.85) / 0.15.
- The latency pressure fed into the shared engine state held U at about 0.946 or below.

## Diagnosis
The latency is pod-level: workers ran at about 7% utilisation and no pod was waiting for a place. Holding machines
cannot cure it, but the single shared state charged it to every organ.

## Mechanism change (commit after cdc8cd9), judged by live set 5
The machine organ now has its own engine view and a release gate
(`omnicompass/nervous_system.node_release_gate`, `tests/test_node_release_gate.py`).

**Its own engine view.**
- It is fed with machine-attributable pressure only: pods waiting for a place.
- It must grant contraction by its own calm, stress and security gates.

**Pods-first coordination** (the rule benchmarked in simulation). There is no release:
- while any HPA is scaling up;
- while latency is breached now.

**Headroom proof.**
- Nothing is pending.
- After the release, the remaining machines run at or below the engine's own utilisation target: used / ((n - 1) per
  node) <= rho.

**Pace.** At most one machine per decision.

Every decision records the gate's reason in the audit, and the trail prints it.
