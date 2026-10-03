# The six organisms: the full grid

Evidence class **S** (models of the plants, not hardware). Every organism runs native (its own controllers) and native with Omni-Compass on top (the bowl law on every muscle, round 6 of `docs/REALMS_PREREGISTRATION.md`) on the same seed, the same load and the same clock. **Size** is the number of copies of the organism governed together on one clock: 1, 10, 100 and 1,000 clusters. **Runs** are paired seeds from 7000 on; 1, 10, 100 and 1,000 runs are the first N of the same set, so each block nests inside the next. Built by `tools/grid.py` from the saved receipts in `results/scale/receipts/`. How to read it: `docs/HOW_TO_READ_THE_RESULTS.md`.

Sources:
- 1x: GitHub Actions workflow `six`, run 37089059426 (#87), job `receipts` 111106802925, transcribed from the job's printed receipt; the run's artifact `six-receipts` (zip SHA-256 `bc69e70c4b22bb27050107543313bb05b46ccf4ed926e1a1e6fb8fd09a89b31f`) holds the same table.
- 10x: running on GitHub
- 100x: running on GitHub
- 1000x: running on GitHub
- 1,000 runs at 1,000 clusters is not run: about 6,000 machine-hours, beyond the machines available.

## Work per energy, with Omni-Compass on top against native (higher is better)

| Organism (muscles) | 1x, 1 run | 1x, 10 runs | 1x, 100 runs | 1x, 1000 runs | 10x, 1 run | 10x, 10 runs | 10x, 100 runs | 10x, 1000 runs | 100x, 1 run | 100x, 10 runs | 100x, 100 runs | 100x, 1000 runs | 1000x, 1 run | 1000x, 10 runs | 1000x, 100 runs | 1000x, 1000 runs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud (345) | +0.089% | +0.099% | +0.092% | +0.092% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Physics / Robotics / Autonomous (262) | +0.077% | +0.093% | +0.085% | +0.085% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Energy / Facility / Industrial (282) | +0.205% | +0.203% | +0.201% | +0.201% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Distribution / Specialized (337) | +0.083% | +0.094% | +0.086% | +0.087% | running | running | running | running | running | running | running | running | running | running | running | not run |
| The four stacked, duplicates kept (1226) | +0.152% | +0.153% | +0.154% | +0.154% | running | running | running | running | running | running | running | running | running | running | running | not run |
| The whole tower, every muscle once (656) | +0.195% | +0.196% | +0.195% | +0.194% | running | running | running | running | running | running | running | running | running | running | running | not run |

## Energy, with Omni-Compass on top against native (lower is better)

| Organism (muscles) | 1x, 1 run | 1x, 10 runs | 1x, 100 runs | 1x, 1000 runs | 10x, 1 run | 10x, 10 runs | 10x, 100 runs | 10x, 1000 runs | 100x, 1 run | 100x, 10 runs | 100x, 100 runs | 100x, 1000 runs | 1000x, 1 run | 1000x, 10 runs | 1000x, 100 runs | 1000x, 1000 runs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud (345) | -0.089% | -0.099% | -0.092% | -0.092% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Physics / Robotics / Autonomous (262) | -0.084% | -0.094% | -0.085% | -0.086% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Energy / Facility / Industrial (282) | -0.204% | -0.202% | -0.200% | -0.200% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Distribution / Specialized (337) | -0.083% | -0.094% | -0.086% | -0.087% | running | running | running | running | running | running | running | running | running | running | running | not run |
| The four stacked, duplicates kept (1226) | -0.151% | -0.153% | -0.154% | -0.154% | running | running | running | running | running | running | running | running | running | running | running | not run |
| The whole tower, every muscle once (656) | -0.197% | -0.196% | -0.194% | -0.194% | running | running | running | running | running | running | running | running | running | running | running | not run |

## Time over the service line, with Omni-Compass on top minus native (percentage points) (lower is better; band first holds where it is at or under 0)

| Organism (muscles) | 1x, 1 run | 1x, 10 runs | 1x, 100 runs | 1x, 1000 runs | 10x, 1 run | 10x, 10 runs | 10x, 100 runs | 10x, 1000 runs | 100x, 1 run | 100x, 10 runs | 100x, 100 runs | 100x, 1000 runs | 1000x, 1 run | 1000x, 10 runs | 1000x, 100 runs | 1000x, 1000 runs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud (345) | -0.019 | -0.016 | -0.016 | -0.016 | running | running | running | running | running | running | running | running | running | running | running | not run |
| Physics / Robotics / Autonomous (262) | -0.021 | -0.011 | -0.012 | -0.011 | running | running | running | running | running | running | running | running | running | running | running | not run |
| Energy / Facility / Industrial (282) | -0.040 | -0.028 | -0.032 | -0.033 | running | running | running | running | running | running | running | running | running | running | running | not run |
| Distribution / Specialized (337) | -0.020 | -0.014 | -0.016 | -0.017 | running | running | running | running | running | running | running | running | running | running | running | not run |
| The four stacked, duplicates kept (1226) | -0.012 | -0.021 | -0.022 | -0.023 | running | running | running | running | running | running | running | running | running | running | running | not run |
| The whole tower, every muscle once (656) | -0.013 | -0.009 | -0.010 | -0.009 | running | running | running | running | running | running | running | running | running | running | running | not run |

## Work done, with Omni-Compass on top against native (equal is the guardrail)

| Organism (muscles) | 1x, 1 run | 1x, 10 runs | 1x, 100 runs | 1x, 1000 runs | 10x, 1 run | 10x, 10 runs | 10x, 100 runs | 10x, 1000 runs | 100x, 1 run | 100x, 10 runs | 100x, 100 runs | 100x, 1000 runs | 1000x, 1 run | 1000x, 10 runs | 1000x, 100 runs | 1000x, 1000 runs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud (345) | +0.000% | +0.000% | +0.000% | -0.000% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Physics / Robotics / Autonomous (262) | -0.007% | -0.001% | -0.000% | -0.001% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Energy / Facility / Industrial (282) | +0.000% | +0.000% | +0.000% | +0.000% | running | running | running | running | running | running | running | running | running | running | running | not run |
| Distribution / Specialized (337) | +0.000% | -0.000% | -0.000% | -0.000% | running | running | running | running | running | running | running | running | running | running | running | not run |
| The four stacked, duplicates kept (1226) | +0.000% | -0.000% | -0.000% | -0.000% | running | running | running | running | running | running | running | running | running | running | running | not run |
| The whole tower, every muscle once (656) | -0.003% | -0.000% | +0.000% | +0.000% | running | running | running | running | running | running | running | running | running | running | running | not run |

## Label by the preregistered rule (chosen by code, never by hand)

| Organism (muscles) | 1x, 1 run | 1x, 10 runs | 1x, 100 runs | 1x, 1000 runs | 10x, 1 run | 10x, 10 runs | 10x, 100 runs | 10x, 1000 runs | 100x, 1 run | 100x, 10 runs | 100x, 100 runs | 100x, 1000 runs | 1000x, 1 run | 1000x, 10 runs | 1000x, 100 runs | 1000x, 1000 runs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud (345) | ONE RUN (no label) | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | running | running | running | running | running | running | running | running | running | running | running | not run |
| Physics / Robotics / Autonomous (262) | ONE RUN (no label) | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | running | running | running | running | running | running | running | running | running | running | running | not run |
| Energy / Facility / Industrial (282) | ONE RUN (no label) | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | running | running | running | running | running | running | running | running | running | running | running | not run |
| Distribution / Specialized (337) | ONE RUN (no label) | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | running | running | running | running | running | running | running | running | running | running | running | not run |
| The four stacked, duplicates kept (1226) | ONE RUN (no label) | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | running | running | running | running | running | running | running | running | running | running | running | not run |
| The whole tower, every muscle once (656) | ONE RUN (no label) | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | SUPERIOR WITHIN GUARDRAILS | running | running | running | running | running | running | running | running | running | running | running | not run |

## Summary of the completed cells

- Cells completed: 24 of 90 (six organisms x 15 size and run cells).
- Band first held: 24 of 24.
- Every knob handed back in every completed cell: True.
- The full receipt of each size, with the 95% interval of every number, is in `results/scale/receipts/`.
