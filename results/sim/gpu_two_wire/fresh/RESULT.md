# The GPU card in simulation: each base alone, and with Omni-Compass on top

Evidence class **S** (a model, not a meter). Seeds 5100-5109, 600 s each, commit `9ec6e50`, 2026-10-03 01:03 UTC. Model: `realms/gpu_card.py`; the law: `omnicompass/bowl.py` and the verdict `omnicompass/verdict.py`.

Omni-Compass never runs the card. It sits on top of what already runs it (the card's own firmware, or an operator's power cap) and moves two settings that base already accepts: the clock ceiling and the power limit. A step down is taken only after a paired trial on the card shows it adds at most 2% to the card's own time on a request; where no step passes, Omni leaves the base exactly as it was. Every comparison below is a base alone against the same base with Omni on top, on the same seeds and the same requests.

## Compute-bound work (matrix products)

### Mean over seeds

| Gauge | The card's firmware alone | Firmware + Omni on top | A fixed 105 W power cap alone | The cap + Omni on top |
|---|---:|---:|---:|---:|
| work per energy (requests per kJ) | 433.2 | 435.3 | 498.3 | 499.5 |
| energy (J) | 68534 | 68206 | 59083 | 58942 |
| requests served | 29696 | 29696 | 29441 | 29441 |
| response, median (ms) | 10.1 | 10.2 | 367.0 | 359.5 |
| response, 95th percentile (ms) | 282.1 | 282.5 | 8369.5 | 8352.8 |
| response, 99th percentile (ms) | 743.8 | 744.7 | 10207.2 | 10192.2 |
| time over the service line (%) | 3.84% | 3.84% | 41.73% | 41.69% |
| hammer blows per second | 1.16 | 1.11 | 8.22 | 8.14 |
| clock reversals per second | 2.23 | 2.16 | 16.02 | 15.88 |
| clock, mean share of top | 0.981 | 0.973 | 0.775 | 0.770 |
| clock, standard deviation | 0.043 | 0.041 | 0.181 | 0.174 |
| temperature, peak (C) | 75.8 | 75.7 | 64.1 | 64.1 |
| temperature, mean (C) | 66.5 | 66.3 | 61.6 | 61.5 |

### With Omni on top against the same base alone (ratios: geometric mean over seeds, 95% interval; time over the line: mean difference)

| Gauge | firmware + Omni on top vs the card's firmware alone | the cap + Omni on top vs a fixed 105 W power cap alone |
|---|---:|---:|
| work per energy | +0.48% (+0.28% to +0.68%) | +0.24% (+0.08% to +0.40%) |
| energy | -0.48% (-0.67% to -0.28%) | -0.24% (-0.40% to -0.08%) |
| response, median | +1.47% (+0.83% to +2.12%) | -1.30% (-2.70% to +0.11%) |
| response, p95 | +0.01% (-0.54% to +0.57%) | -0.17% (-0.34% to -0.01%) |
| response, p99 | +0.02% (-0.10% to +0.15%) | -0.13% (-0.28% to +0.01%) |
| time over the line (pp) | +0.002 (-0.003 to +0.006) | -0.040 (-0.087 to +0.007) |
| requests served | +0.00% (-0.00% to +0.00%) | +0.00% (-0.00% to +0.00%) |

Verdict over all Omni runs: 62 trials, 42 steps allowed, 20 refused. Both wires back at their snapshot after the kill on every seed: True.

## AI token generation (85% of each request waiting on memory)

### Mean over seeds

| Gauge | The card's firmware alone | Firmware + Omni on top | A fixed 105 W power cap alone | The cap + Omni on top |
|---|---:|---:|---:|---:|
| work per energy (requests per kJ) | 435.0 | 452.1 | 502.9 | 515.4 |
| energy (J) | 68250 | 65726 | 59044 | 57653 |
| requests served | 29696 | 29696 | 29696 | 29696 |
| response, median (ms) | 10.0 | 10.1 | 10.2 | 10.3 |
| response, 95th percentile (ms) | 10.1 | 10.2 | 42.9 | 43.0 |
| response, 99th percentile (ms) | 11.0 | 10.9 | 84.1 | 84.2 |
| time over the service line (%) | 0.00% | 0.00% | 0.48% | 0.48% |
| hammer blows per second | 1.03 | 0.68 | 7.74 | 6.77 |
| clock reversals per second | 2.02 | 1.38 | 15.13 | 13.27 |
| clock, mean share of top | 0.988 | 0.954 | 0.891 | 0.867 |
| clock, standard deviation | 0.027 | 0.043 | 0.107 | 0.091 |
| temperature, peak (C) | 75.6 | 74.7 | 64.2 | 64.2 |
| temperature, mean (C) | 66.3 | 65.0 | 61.6 | 60.8 |

### With Omni on top against the same base alone (ratios: geometric mean over seeds, 95% interval; time over the line: mean difference)

| Gauge | firmware + Omni on top vs the card's firmware alone | the cap + Omni on top vs a fixed 105 W power cap alone |
|---|---:|---:|
| work per energy | +3.86% (+1.51% to +6.27%) | +2.42% (+1.08% to +3.79%) |
| energy | -3.72% (-5.90% to -1.49%) | -2.37% (-3.65% to -1.06%) |
| response, median | +0.70% (+0.06% to +1.34%) | +0.12% (-0.11% to +0.36%) |
| response, p95 | +0.26% (-0.00% to +0.52%) | +0.03% (-0.04% to +0.09%) |
| response, p99 | -0.52% (-2.05% to +1.02%) | +0.06% (-0.05% to +0.17%) |
| time over the line (pp) | +0.000 (+0.000 to +0.000) | +0.000 (+0.000 to +0.000) |
| requests served | +0.00% (-0.00% to +0.00%) | +0.00% (+0.00% to +0.00%) |

Verdict over all Omni runs: 279 trials, 259 steps allowed, 20 refused. Both wires back at their snapshot after the kill on every seed: True.

Requests served are the same work in every arm (the stream is the seed's); a backlog left at the end is in the JSON. A model written by the same people who wrote the law is not an independent test. The card's power curve (dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any product. The number that counts is a rented card's own meter.
