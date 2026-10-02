# The whole stacks with the real card inside

Run 2026-10-02 08:59 UTC, commit `c908054053e9`, 3 paired repetition(s), seeds [6000, 6001, 6002], 240 steps of 2.0 s per arm. Card: the real GPU, its own meter; start power limit 150.0 W; response-time line 782.3 ms (ten bare service times). One engine on everything in the Omni arm: the bowl law on every simulated muscle and on the card's two wires. Harness `tools/run_hil.py`.

The simulated stacks are models (evidence S). The card's energy and requests are its own meter (evidence P). Work per energy: (work Omni / work native) / (energy Omni / energy native) - 1; for the stacks work is the mean over plants of each plant's ratio; *both* counts the card as one more plant and adds its joules.

## Omni against native, by organism (mean over repetitions, 95% interval when there are two or more)

| Organism | Part | Label | Work per energy | Work | Energy | Violations (pp) |
|---|---|---|---:|---:|---:|---:|
| Compute / AI / Cloud | stacks (model) | SUPERIOR WITHIN GUARDRAILS | +0.32% (+0.28 to +0.37) | -0.02% (-0.04 to +0.00) | -0.34% (-0.40 to -0.28) | +0.25 (+0.14 to +0.37) |
| Compute / AI / Cloud | card (meter) | SUPERIOR WITHIN GUARDRAILS | +2.00% (+0.81 to +3.20) | +0.00% (+0.00 to +0.00) | -1.96% (-3.11 to -0.82) | +0.00 (+0.00 to +0.00) |
| Compute / AI / Cloud | both | SUPERIOR WITHIN GUARDRAILS | +0.32% (+0.28 to +0.37) | -0.02% (-0.04 to +0.00) | -0.34% (-0.40 to -0.28) | +0.25 (+0.14 to +0.37) |
| Physics / Robotics / Autonomous | stacks (model) | SUPERIOR WITHIN GUARDRAILS | +0.24% (+0.20 to +0.27) | -0.02% (-0.05 to +0.02) | -0.25% (-0.31 to -0.20) | +0.24 (+0.04 to +0.44) |
| Physics / Robotics / Autonomous | card (meter) | NONINFERIOR / INCONCLUSIVE | +2.68% (-1.28 to +6.64) | +0.00% (+0.00 to +0.00) | -2.59% (-6.33 to +1.14) | +0.00 (+0.00 to +0.00) |
| Physics / Robotics / Autonomous | both | SUPERIOR WITHIN GUARDRAILS | +0.24% (+0.20 to +0.27) | -0.02% (-0.05 to +0.02) | -0.25% (-0.31 to -0.20) | +0.24 (+0.04 to +0.44) |
| Energy / Facility / Industrial | stacks (model) | SUPERIOR WITHIN GUARDRAILS | +0.21% (+0.18 to +0.23) | -0.02% (-0.05 to +0.02) | -0.22% (-0.24 to -0.21) | +0.22 (+0.06 to +0.38) |
| Energy / Facility / Industrial | card (meter) | SUPERIOR WITHIN GUARDRAILS | +2.75% (+2.24 to +3.26) | +0.00% (+0.00 to +0.00) | -2.68% (-3.16 to -2.19) | +0.00 (+0.00 to +0.00) |
| Energy / Facility / Industrial | both | SUPERIOR WITHIN GUARDRAILS | +0.21% (+0.18 to +0.23) | -0.02% (-0.05 to +0.02) | -0.22% (-0.24 to -0.21) | +0.22 (+0.06 to +0.38) |
| Distribution / Specialized | stacks (model) | SUPERIOR WITHIN GUARDRAILS | +0.25% (+0.22 to +0.29) | -0.02% (-0.05 to +0.02) | -0.27% (-0.32 to -0.22) | +0.26 (+0.05 to +0.46) |
| Distribution / Specialized | card (meter) | SUPERIOR WITHIN GUARDRAILS | +2.37% (+1.34 to +3.40) | +0.00% (+0.00 to +0.00) | -2.32% (-3.30 to -1.33) | +0.00 (+0.00 to +0.00) |
| Distribution / Specialized | both | SUPERIOR WITHIN GUARDRAILS | +0.25% (+0.22 to +0.29) | -0.01% (-0.05 to +0.02) | -0.27% (-0.32 to -0.22) | +0.26 (+0.05 to +0.46) |
| The four stacked, duplicates kept (1,226) | stacks (model) | SUPERIOR WITHIN GUARDRAILS | +0.21% (+0.19 to +0.22) | -0.02% (-0.04 to -0.01) | -0.23% (-0.23 to -0.22) | +0.23 (+0.22 to +0.25) |
| The four stacked, duplicates kept (1,226) | card (meter) | SUPERIOR WITHIN GUARDRAILS | +1.63% (+0.45 to +2.81) | +0.00% (+0.00 to +0.00) | -1.60% (-2.75 to -0.46) | +0.00 (+0.00 to +0.00) |
| The four stacked, duplicates kept (1,226) | both | SUPERIOR WITHIN GUARDRAILS | +0.21% (+0.19 to +0.22) | -0.02% (-0.03 to -0.01) | -0.23% (-0.23 to -0.22) | +0.23 (+0.22 to +0.25) |
| The whole tower (656 muscles) | stacks (model) | SUPERIOR WITHIN GUARDRAILS | +0.23% (+0.22 to +0.23) | -0.01% (-0.02 to +0.00) | -0.24% (-0.24 to -0.23) | +0.18 (+0.06 to +0.29) |
| The whole tower (656 muscles) | card (meter) | SUPERIOR WITHIN GUARDRAILS | +2.62% (+1.64 to +3.60) | +0.00% (+0.00 to +0.00) | -2.56% (-3.49 to -1.62) | +0.00 (+0.00 to +0.00) |
| The whole tower (656 muscles) | both | SUPERIOR WITHIN GUARDRAILS | +0.23% (+0.22 to +0.23) | -0.01% (-0.02 to +0.00) | -0.24% (-0.24 to -0.23) | +0.18 (+0.06 to +0.29) |

## The card's receipts, by arm

| Organism | Rep | Arm | Card energy (J) | Requests served | Not served | p95 (ms) | Limit start → end (W) | Governor exit |
|---|---:|---|---:|---:|---:|---:|---|---|
| Compute / AI / Cloud | 1 | native | 54600 | 2949 | 0 | 506.1 | 150.0 → 150.0 | None |
| Compute / AI / Cloud | 1 | omni | 53764 | 2949 | 0 | 845.1 | 150.0 → 150.0 | 0 |
| Compute / AI / Cloud | 2 | native | 54742 | 2949 | 0 | 496.1 | 150.0 → 150.0 | None |
| Compute / AI / Cloud | 2 | omni | 53401 | 2949 | 0 | 775.7 | 150.0 → 150.0 | 0 |
| Compute / AI / Cloud | 3 | native | 54861 | 2949 | 0 | 501.5 | 150.0 → 150.0 | None |
| Compute / AI / Cloud | 3 | omni | 53814 | 2949 | 0 | 667.4 | 150.0 → 150.0 | 0 |
| Physics / Robotics / Autonomous | 1 | native | 55127 | 2949 | 0 | 505.5 | 150.0 → 150.0 | None |
| Physics / Robotics / Autonomous | 1 | omni | 52787 | 2949 | 0 | 662.6 | 150.0 → 150.0 | 0 |
| Physics / Robotics / Autonomous | 2 | native | 54655 | 2949 | 0 | 501.3 | 150.0 → 150.0 | None |
| Physics / Robotics / Autonomous | 2 | omni | 53942 | 2949 | 0 | 745.1 | 150.0 → 150.0 | 0 |
| Physics / Robotics / Autonomous | 3 | native | 55439 | 2949 | 0 | 500.2 | 150.0 → 150.0 | None |
| Physics / Robotics / Autonomous | 3 | omni | 54202 | 2949 | 0 | 850.9 | 150.0 → 150.0 | 0 |
| Energy / Facility / Industrial | 1 | native | 55193 | 2949 | 0 | 505.5 | 150.0 → 150.0 | None |
| Energy / Facility / Industrial | 1 | omni | 53617 | 2949 | 0 | 872.4 | 150.0 → 150.0 | 0 |
| Energy / Facility / Industrial | 2 | native | 55267 | 2949 | 0 | 502.0 | 150.0 → 150.0 | None |
| Energy / Facility / Industrial | 2 | omni | 53771 | 2949 | 0 | 710.7 | 150.0 → 150.0 | 0 |
| Energy / Facility / Industrial | 3 | native | 55558 | 2949 | 0 | 494.6 | 150.0 → 150.0 | None |
| Energy / Facility / Industrial | 3 | omni | 54188 | 2949 | 0 | 697.9 | 150.0 → 150.0 | 0 |
| Distribution / Specialized | 1 | native | 55063 | 2949 | 0 | 503.1 | 150.0 → 150.0 | None |
| Distribution / Specialized | 1 | omni | 54016 | 2949 | 0 | 690.9 | 150.0 → 150.0 | 0 |
| Distribution / Specialized | 2 | native | 55171 | 2949 | 0 | 498.3 | 150.0 → 150.0 | None |
| Distribution / Specialized | 2 | omni | 53871 | 2949 | 0 | 731.5 | 150.0 → 150.0 | 0 |
| Distribution / Specialized | 3 | native | 54542 | 2949 | 0 | 494.4 | 150.0 → 150.0 | None |
| Distribution / Specialized | 3 | omni | 53074 | 2949 | 0 | 723.6 | 150.0 → 150.0 | 0 |
| The four stacked, duplicates kept (1,226) | 1 | native | 54744 | 2949 | 0 | 492.5 | 150.0 → 150.0 | None |
| The four stacked, duplicates kept (1,226) | 1 | omni | 53733 | 2949 | 0 | 914.1 | 150.0 → 150.0 | 0 |
| The four stacked, duplicates kept (1,226) | 2 | native | 54655 | 2949 | 0 | 500.6 | 150.0 → 150.0 | None |
| The four stacked, duplicates kept (1,226) | 2 | omni | 53621 | 2949 | 0 | 888.9 | 150.0 → 150.0 | 0 |
| The four stacked, duplicates kept (1,226) | 3 | native | 54589 | 2949 | 0 | 499.5 | 150.0 → 150.0 | None |
| The four stacked, duplicates kept (1,226) | 3 | omni | 54004 | 2949 | 0 | 935.5 | 150.0 → 150.0 | 0 |
| The whole tower (656 muscles) | 1 | native | 54565 | 2949 | 0 | 498.3 | 150.0 → 150.0 | None |
| The whole tower (656 muscles) | 1 | omni | 53012 | 2949 | 0 | 792.3 | 150.0 → 150.0 | 0 |
| The whole tower (656 muscles) | 2 | native | 54983 | 2949 | 0 | 498.4 | 150.0 → 150.0 | None |
| The whole tower (656 muscles) | 2 | omni | 53810 | 2949 | 0 | 752.9 | 150.0 → 150.0 | 0 |
| The whole tower (656 muscles) | 3 | native | 55060 | 2949 | 0 | 497.4 | 150.0 → 150.0 | None |
| The whole tower (656 muscles) | 3 | omni | 53579 | 2949 | 0 | 598.7 | 150.0 → 150.0 | 0 |

## Validity

- Every arm ended with the card at its start limit and its own clock range; every simulated knob was handed back; the card's governor exited cleanly.

Raw: every arm's `arm.json`, `smi.csv` (the card's own samples), `latency.csv`, `requests.csv`, `audit.jsonl`; checksums in `SHA256SUMS.txt`.
