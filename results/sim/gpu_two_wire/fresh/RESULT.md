# The two-wire GPU card, in simulation

Evidence class **S** (a model, not a meter). Seeds 5100-5109, 600 s each, commit `65c3083`, 2026-10-02 21:47 UTC. Model and arms: `realms/gpu_card.py`; the law: `omnicompass/bowl.py`. The frozen engine is not used here; this is the bowl law as its own arm.

- **native**: the card as shipped, 150 W limit, firmware boost up a bin and hammer down three at the limit;
- **preset**: a fixed 105 W limit (70%), set and left, as an operator would;
- **old governor**: the shipped one-wire GPU governor (its defaults), the power limit only;
- **bowl**: Omni through two wires, the clock ceiling (up) and the power limit (down, the lid), pulling the service position (response time) to the middle of its bowl, racing at full speed while the card is saturated and never pacing under the clock or the draw the card reaches on its own while busy (amendment 6); both wires restored to their snapshot at 90% of the run. **Service** profile (the default and the benchmark's arm): down gain 0.01; **batch** profile: down gain 0.02, for work nobody waits on answer by answer.

## Mean over seeds

| Gauge | Native | Preset | Old governor | Bowl, service | Bowl, batch |
|---|---:|---:|---:|---:|---:|
| work per energy (requests per kJ) | 433.2 | 498.3 | 433.5 | 445.3 | 451.9 |
| energy (J) | 68534 | 59083 | 68488 | 66683 | 65729 |
| requests served | 29696 | 29441 | 29696 | 29696 | 29696 |
| response, median (ms) | 10.1 | 367.0 | 10.1 | 11.0 | 11.4 |
| response, 95th percentile (ms) | 282.1 | 8369.5 | 282.7 | 281.1 | 276.8 |
| response, 99th percentile (ms) | 743.8 | 10207.2 | 744.0 | 746.3 | 744.6 |
| time over the service line (%) | 3.84% | 41.73% | 3.84% | 3.82% | 3.79% |
| hammer blows per second | 1.16 | 8.22 | 1.24 | 0.98 | 0.96 |
| clock reversals per second | 2.23 | 16.02 | 2.35 | 1.90 | 1.87 |
| clock, mean share of top | 0.981 | 0.775 | 0.980 | 0.931 | 0.904 |
| clock, standard deviation | 0.043 | 0.181 | 0.046 | 0.055 | 0.074 |
| temperature, peak (C) | 75.8 | 64.1 | 75.8 | 75.1 | 74.9 |
| temperature, mean (C) | 66.5 | 61.6 | 66.5 | 65.5 | 65.0 |

## Paired against native (95% interval over seeds)

| Gauge | Preset | Old governor | Bowl, service | Bowl, batch |
|---|---:|---:|---:|---:|
| work per energy | +15.0% (+14.0% to +16.0%) | +0.1% (+0.0% to +0.1%) | +2.8% (+1.8% to +3.8%) | +4.3% (+2.7% to +5.9%) |
| energy | -13.8% (-14.8% to -12.8%) | -0.1% (-0.1% to -0.0%) | -2.7% (-3.7% to -1.7%) | -4.1% (-5.5% to -2.6%) |
| time over the line (pp) | +37.89 (+30.51 to +45.28) | +0.00 (-0.00 to +0.01) | -0.02 (-0.05 to +0.01) | -0.05 (-0.10 to +0.01) |
| response p95 | +19312.5% (+3208.6% to +35416.4%) | +1.9% (-0.9% to +4.6%) | -1.3% (-6.2% to +3.6%) | -1.7% (-9.6% to +6.3%) |
| hammer blows | +2426.6% (-1602.5% to +6455.8%) | +22.8% (-11.1% to +56.7%) | -16.2% (-27.1% to -5.2%) | -17.0% (-25.8% to -8.2%) |

Both wires back at their snapshot after the kill on every seed: True. Requests served are the same work on every arm (the stream is the seed's); a backlog left at the end is in the JSON.

A model written by the same people who wrote the law is not an independent test. The card's power curve (dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any product. The number that counts is a rented card's own meter.
