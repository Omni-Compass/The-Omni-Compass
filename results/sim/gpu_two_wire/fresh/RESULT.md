# The two-wire GPU card, in simulation

Evidence class **S** (a model, not a meter). Seeds 5100-5109, 600 s each, commit `0a01f1b`, 2026-10-02 05:36 UTC. Model and arms: `realms/gpu_card.py`; the law: `omnicompass/bowl.py`. The frozen engine is not used here; this is the bowl law as its own arm.

- **native**: the card as shipped, 150 W limit, firmware boost up a bin and hammer down three at the limit;
- **preset**: a fixed 105 W limit (70%), set and left, as an operator would;
- **old governor**: the shipped one-wire GPU governor (its defaults), the power limit only;
- **bowl**: Omni through two wires, the clock ceiling (up) and the power limit (down, the lid), pulling the service position (the worse of response time and busy share) to the middle of its bowl; both wires restored to their snapshot at 90% of the run.

## Mean over seeds

| Gauge | Native | Preset | Old governor | Bowl |
|---|---:|---:|---:|---:|
| work per energy (requests per kJ) | 433.2 | 498.3 | 433.5 | 472.0 |
| energy (J) | 68534 | 59083 | 68488 | 62917 |
| requests served | 29696 | 29441 | 29696 | 29696 |
| response, median (ms) | 10.1 | 367.0 | 10.1 | 11.7 |
| response, 95th percentile (ms) | 282.1 | 8369.5 | 282.7 | 292.2 |
| response, 99th percentile (ms) | 743.8 | 10207.2 | 744.0 | 762.3 |
| time over the service line (%) | 3.84% | 41.73% | 3.84% | 4.02% |
| hammer blows per second | 1.16 | 8.22 | 1.24 | 1.04 |
| clock reversals per second | 2.23 | 16.02 | 2.35 | 2.21 |
| clock, mean share of top | 0.981 | 0.775 | 0.980 | 0.802 |
| clock, standard deviation | 0.043 | 0.181 | 0.046 | 0.153 |
| temperature, peak (C) | 75.8 | 64.1 | 75.8 | 74.7 |
| temperature, mean (C) | 66.5 | 61.6 | 66.5 | 63.4 |

## Paired against native (95% interval over seeds)

| Gauge | Preset | Old governor | Bowl |
|---|---:|---:|---:|
| work per energy | +15.0% (+14.0% to +16.0%) | +0.1% (+0.0% to +0.1%) | +9.0% (+8.0% to +10.0%) |
| energy | -13.8% (-14.8% to -12.8%) | -0.1% (-0.1% to -0.0%) | -8.2% (-9.0% to -7.4%) |
| time over the line (pp) | +37.89 (+30.51 to +45.28) | +0.00 (-0.00 to +0.01) | +0.18 (-0.12 to +0.48) |
| response p95 | +19312.5% (+3208.6% to +35416.4%) | +1.9% (-0.9% to +4.6%) | +37.1% (+6.8% to +67.3%) |
| hammer blows | +2426.6% (-1602.5% to +6455.8%) | +22.8% (-11.1% to +56.7%) | -11.2% (-14.8% to -7.7%) |

Both wires back at their snapshot after the kill on every seed: True. Requests served are the same work on every arm (the stream is the seed's); a backlog left at the end is in the JSON.

A model written by the same people who wrote the law is not an independent test. The card's power curve (dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any product. The number that counts is a rented card's own meter.
