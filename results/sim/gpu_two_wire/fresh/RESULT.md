# The two-wire GPU card, in simulation

Evidence class **S** (a model, not a meter). Seeds 5100-5109, 600 s each, commit `05eab70`, 2026-10-02 22:04 UTC. Model and arms: `realms/gpu_card.py`; the law: `omnicompass/bowl.py`. The frozen engine is not used here; this is the bowl law as its own arm.

- **native**: the card as shipped, 150 W limit, firmware boost up a bin and hammer down three at the limit;
- **preset**: a fixed 105 W limit (70%), set and left, as an operator would;
- **old governor**: the shipped one-wire GPU governor (its defaults), the power limit only;
- **bowl**: Omni through two wires, the clock ceiling (up) and the power limit (down, the lid), pulling the service position (response time) to the middle of its bowl, racing at full speed while the card is saturated and never pacing under the clock or the draw the card reaches on its own while busy (amendment 6); both wires restored to their snapshot at 90% of the run. **Service** profile (the default and the benchmark's arm): down gain 0.0125, bowl center 0.4, speed floor 3% above the card's own busy clock; **batch** profile: down gain 0.015, center 0.5, floor at the card's own busy clock, for work nobody waits on answer by answer.

## Mean over seeds

| Gauge | Native | Preset | Old governor | Bowl, service | Bowl, batch |
|---|---:|---:|---:|---:|---:|
| work per energy (requests per kJ) | 433.2 | 498.3 | 433.5 | 449.8 | 451.8 |
| energy (J) | 68534 | 59083 | 68488 | 66029 | 65745 |
| requests served | 29696 | 29441 | 29696 | 29696 | 29696 |
| response, median (ms) | 10.1 | 367.0 | 10.1 | 11.2 | 11.4 |
| response, 95th percentile (ms) | 282.1 | 8369.5 | 282.7 | 278.3 | 276.8 |
| response, 99th percentile (ms) | 743.8 | 10207.2 | 744.0 | 745.8 | 744.6 |
| time over the service line (%) | 3.84% | 41.73% | 3.84% | 3.80% | 3.79% |
| hammer blows per second | 1.16 | 8.22 | 1.24 | 0.95 | 0.96 |
| clock reversals per second | 2.23 | 16.02 | 2.35 | 1.85 | 1.88 |
| clock, mean share of top | 0.981 | 0.775 | 0.980 | 0.913 | 0.905 |
| clock, standard deviation | 0.043 | 0.181 | 0.046 | 0.068 | 0.074 |
| temperature, peak (C) | 75.8 | 64.1 | 75.8 | 74.9 | 74.9 |
| temperature, mean (C) | 66.5 | 61.6 | 66.5 | 65.1 | 65.0 |

## Paired against native (ratios: geometric mean over seeds with its 95% interval; time over the line: mean difference)

| Gauge | Preset | Old governor | Bowl, service | Bowl, batch |
|---|---:|---:|---:|---:|
| work per energy | +15.0% (+14.0% to +16.0%) | +0.1% (+0.0% to +0.1%) | +3.8% (+2.4% to +5.2%) | +4.2% (+2.7% to +5.8%) |
| energy | -13.8% (-14.8% to -12.8%) | -0.1% (-0.1% to -0.0%) | -3.7% (-4.9% to -2.4%) | -4.1% (-5.5% to -2.6%) |
| time over the line (pp) | +37.89 (+30.51 to +45.28) | +0.00 (-0.00 to +0.01) | -0.04 (-0.08 to +0.01) | -0.05 (-0.10 to +0.01) |
| response p95 | +9215.1% (+3462.0% to +24260.4%) | +1.8% (-0.8% to +4.5%) | -2.3% (-9.7% to +5.6%) | -2.3% (-10.4% to +6.6%) |
| hammer blows | +866.1% (+337.1% to +2035.3%) | +17.6% (-3.6% to +43.5%) | -20.5% (-33.3% to -5.2%) | -17.5% (-26.5% to -7.3%) |

Both wires back at their snapshot after the kill on every seed: True. Requests served are the same work on every arm (the stream is the seed's); a backlog left at the end is in the JSON.

A model written by the same people who wrote the law is not an independent test. The card's power curve (dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any product. The number that counts is a rented card's own meter.
