# The six organisms: the full grid

Evidence class **S** (models of the plants, not hardware). Every organism runs native (its own controllers) and with Omni-Compass (the bowl law on every muscle) on the same seed, the same load and the same clock. Size is the number of copies of the organism governed together on one clock (1, 10, 100, 1,000 clusters). Runs are paired seeds from 7000 on; 1, 10, 100 and 1,000 runs are the first N runs of the same set, so each block nests inside the next.

Sources: 1x, GitHub Actions run 37030241989; 10x, run 37030246124 (both on commit 7ab3965, 60 of 60 pieces successful). 100x (run 37030250866, 1,000 runs) and 1,000x (run 37030254384, 100 runs) are running and will be entered here when they finish. 1,000 runs at 1,000x is beyond the free GitHub machines and is not run.

Band first: no win unless the time over the service line is no higher than native's. In every cell completed so far it is higher, so band first is **not held** anywhere yet; the work-per-energy gain is real, but it is bought with time over the line. Closing that is the open work on the engine. Every knob was handed back in every run.

## Work per energy, Omni-Compass against native (%)

| Organism | 1x, 1 run | 1x, 10 runs | 1x, 100 runs | 1x, 1000 runs | 10x, 1 run | 10x, 10 runs | 10x, 100 runs | 10x, 1000 runs | 100x, 1 run | 100x, 10 runs | 100x, 100 runs | 100x, 1000 runs | 1000x, 1 run | 1000x, 10 runs | 1000x, 100 runs | 1000x, 1000 runs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 Compute / AI / Cloud (345) | +0.301% | +0.313% | +0.304% | +0.301% | +0.310% | +0.293% | +0.289% | +0.288% | running | running | running | running | running | running | running | not run |
| 2 Physics / Robotics / Autonomous (262) | +0.200% | +0.239% | +0.226% | +0.225% | +0.231% | +0.222% | +0.220% | +0.220% | running | running | running | running | running | running | running | not run |
| 3 Energy / Facility / Industrial (282) | +0.197% | +0.209% | +0.208% | +0.208% | +0.198% | +0.199% | +0.199% | +0.199% | running | running | running | running | running | running | running | not run |
| 4 Distribution / Specialized (337) | +0.215% | +0.258% | +0.247% | +0.247% | +0.247% | +0.240% | +0.237% | +0.237% | running | running | running | running | running | running | running | not run |
| 5 The four stacked, duplicates kept (1,226) | +0.213% | +0.210% | +0.211% | +0.210% | +0.215% | +0.214% | +0.214% | +0.214% | running | running | running | running | running | running | running | not run |
| 6 The whole tower, every muscle once (656) | +0.219% | +0.226% | +0.225% | +0.224% | +0.220% | +0.217% | +0.216% | +0.216% | running | running | running | running | running | running | running | not run |

## Time over the service line, Omni-Compass minus native (percentage points; above 0 means band first not held)

| Organism | 1x, 1 run | 1x, 10 runs | 1x, 100 runs | 1x, 1000 runs | 10x, 1 run | 10x, 10 runs | 10x, 100 runs | 10x, 1000 runs | 100x, 1 run | 100x, 10 runs | 100x, 100 runs | 100x, 1000 runs | 1000x, 1 run | 1000x, 10 runs | 1000x, 100 runs | 1000x, 1000 runs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 Compute / AI / Cloud (345) | +0.258 | +0.290 | +0.263 | +0.266 | +0.256 | +0.268 | +0.264 | +0.266 | running | running | running | running | running | running | running | not run |
| 2 Physics / Robotics / Autonomous (262) | +0.200 | +0.241 | +0.225 | +0.237 | +0.236 | +0.242 | +0.240 | +0.243 | running | running | running | running | running | running | running | not run |
| 3 Energy / Facility / Industrial (282) | +0.177 | +0.226 | +0.205 | +0.215 | +0.205 | +0.215 | +0.214 | +0.216 | running | running | running | running | running | running | running | not run |
| 4 Distribution / Specialized (337) | +0.255 | +0.266 | +0.247 | +0.254 | +0.248 | +0.255 | +0.256 | +0.256 | running | running | running | running | running | running | running | not run |
| 5 The four stacked, duplicates kept (1,226) | +0.277 | +0.245 | +0.249 | +0.250 | +0.246 | +0.251 | +0.249 | +0.249 | running | running | running | running | running | running | running | not run |
| 6 The whole tower, every muscle once (656) | +0.189 | +0.202 | +0.185 | +0.188 | +0.191 | +0.190 | +0.189 | +0.189 | running | running | running | running | running | running | running | not run |

## Energy, 1,000 runs (%)

| Organism | 1x | 10x | 100x | 1,000x |
|---|---:|---:|---:|---:|
| 1 Compute / AI / Cloud (345) | -0.318% | -0.305% | running | running |
| 2 Physics / Robotics / Autonomous (262) | -0.240% | -0.234% | running | running |
| 3 Energy / Facility / Industrial (282) | -0.221% | -0.213% | running | running |
| 4 Distribution / Specialized (337) | -0.263% | -0.252% | running | running |
| 5 The four stacked, duplicates kept (1,226) | -0.226% | -0.230% | running | running |
| 6 The whole tower, every muscle once (656) | -0.235% | -0.228% | running | running |

Work fell by 0.01% to 0.02% in every cell; energy fell by 0.21% to 0.32%. 95% intervals for every number are in the run receipts (the receipts job of each run prints them in full).
