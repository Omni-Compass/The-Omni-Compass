# The GPU card in simulation: each base alone, and with Omni-Compass on top

Evidence class **S** (a model, not a meter). Seeds 5000-5009, 600 s each, commit `9ec6e50`, 2026-10-03 01:03 UTC. Model: `realms/gpu_card.py`; the law: `omnicompass/bowl.py` and the verdict `omnicompass/verdict.py`.

Omni-Compass never runs the card. It sits on top of what already runs it (the card's own firmware, or an operator's power cap) and moves two settings that base already accepts: the clock ceiling and the power limit. A step down is taken only after a paired trial on the card shows it adds at most 2% to the card's own time on a request; where no step passes, Omni leaves the base exactly as it was. Every comparison below is a base alone against the same base with Omni on top, on the same seeds and the same requests.

## Compute-bound work (matrix products)

### Mean over seeds

| Gauge | The card's firmware alone | Firmware + Omni on top | A fixed 105 W power cap alone | The cap + Omni on top |
|---|---:|---:|---:|---:|
| work per energy (requests per kJ) | 432.1 | 435.2 | 498.0 | 498.5 |
| energy (J) | 68760 | 68282 | 59412 | 59352 |
| requests served | 29719 | 29719 | 29592 | 29592 |
| response, median (ms) | 10.1 | 10.2 | 306.5 | 306.2 |
| response, 95th percentile (ms) | 122.1 | 122.9 | 6942.1 | 6941.8 |
| response, 99th percentile (ms) | 602.0 | 602.0 | 8221.0 | 8220.7 |
| time over the service line (%) | 2.80% | 2.80% | 40.30% | 40.28% |
| hammer blows per second | 0.95 | 0.89 | 8.39 | 8.34 |
| clock reversals per second | 1.80 | 1.70 | 16.33 | 16.24 |
| clock, mean share of top | 0.984 | 0.972 | 0.777 | 0.775 |
| clock, standard deviation | 0.041 | 0.039 | 0.178 | 0.176 |
| temperature, peak (C) | 75.4 | 75.1 | 64.1 | 64.1 |
| temperature, mean (C) | 66.6 | 66.4 | 61.8 | 61.7 |

### With Omni on top against the same base alone (ratios: geometric mean over seeds, 95% interval; time over the line: mean difference)

| Gauge | firmware + Omni on top vs the card's firmware alone | the cap + Omni on top vs a fixed 105 W power cap alone |
|---|---:|---:|
| work per energy | +0.70% (+0.54% to +0.86%) | +0.10% (+0.02% to +0.18%) |
| energy | -0.70% (-0.85% to -0.54%) | -0.10% (-0.18% to -0.02%) |
| response, median | +1.56% (+1.12% to +2.01%) | -1.27% (-3.80% to +1.33%) |
| response, p95 | -0.84% (-4.10% to +2.52%) | -0.01% (-0.02% to +0.01%) |
| response, p99 | -0.09% (-0.37% to +0.20%) | -0.00% (-0.01% to +0.01%) |
| time over the line (pp) | -0.001 (-0.010 to +0.008) | -0.020 (-0.061 to +0.021) |
| requests served | +0.00% (-0.00% to +0.00%) | +0.00% (-0.00% to +0.00%) |

Verdict over all Omni runs: 51 trials, 28 steps allowed, 20 refused. Both wires back at their snapshot after the kill on every seed: True.

## AI token generation (85% of each request waiting on memory)

### Mean over seeds

| Gauge | The card's firmware alone | Firmware + Omni on top | A fixed 105 W power cap alone | The cap + Omni on top |
|---|---:|---:|---:|---:|
| work per energy (requests per kJ) | 433.8 | 448.8 | 500.4 | 511.2 |
| energy (J) | 68505 | 66290 | 59393 | 58164 |
| requests served | 29726 | 29726 | 29726 | 29726 |
| response, median (ms) | 10.0 | 10.1 | 10.2 | 10.2 |
| response, 95th percentile (ms) | 10.1 | 10.2 | 10.7 | 10.7 |
| response, 99th percentile (ms) | 11.5 | 11.5 | 41.7 | 41.7 |
| time over the service line (%) | 0.02% | 0.02% | 0.10% | 0.10% |
| hammer blows per second | 0.85 | 0.68 | 7.89 | 6.97 |
| clock reversals per second | 1.65 | 1.35 | 15.40 | 13.63 |
| clock, mean share of top | 0.989 | 0.961 | 0.893 | 0.872 |
| clock, standard deviation | 0.025 | 0.038 | 0.104 | 0.090 |
| temperature, peak (C) | 75.2 | 74.3 | 64.2 | 64.2 |
| temperature, mean (C) | 66.5 | 65.3 | 61.8 | 61.1 |

### With Omni on top against the same base alone (ratios: geometric mean over seeds, 95% interval; time over the line: mean difference)

| Gauge | firmware + Omni on top vs the card's firmware alone | the cap + Omni on top vs a fixed 105 W power cap alone |
|---|---:|---:|
| work per energy | +3.36% (+0.62% to +6.17%) | +2.13% (+0.80% to +3.48%) |
| energy | -3.25% (-5.81% to -0.62%) | -2.09% (-3.37% to -0.79%) |
| response, median | +0.55% (-0.08% to +1.18%) | +0.07% (-0.09% to +0.23%) |
| response, p95 | +0.29% (+0.06% to +0.53%) | +0.00% (+0.00% to +0.00%) |
| response, p99 | +0.02% (-0.02% to +0.05%) | +0.00% (+0.00% to +0.00%) |
| time over the line (pp) | +0.000 (+0.000 to +0.000) | +0.000 (+0.000 to +0.000) |
| requests served | +0.00% (+0.00% to +0.00%) | +0.00% (+0.00% to +0.00%) |

Verdict over all Omni runs: 255 trials, 235 steps allowed, 20 refused. Both wires back at their snapshot after the kill on every seed: True.

Requests served are the same work in every arm (the stream is the seed's); a backlog left at the end is in the JSON. A model written by the same people who wrote the law is not an independent test. The card's power curve (dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any product. The number that counts is a rented card's own meter.
