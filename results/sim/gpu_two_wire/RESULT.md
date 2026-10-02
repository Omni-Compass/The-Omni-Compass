# The two-wire GPU card, in simulation

Evidence class **S** (a model, not a meter). Seeds 5000-5009, 600 s each, commit `36f2936`, 2026-10-02 05:18 UTC. Model and arms: `realms/gpu_card.py`; the law: `omnicompass/bowl.py`. The frozen engine is not used here; this is the bowl law as its own arm.

- **native**: the card as shipped, 150 W limit, firmware boost up a bin and hammer down three at the limit;
- **preset**: a fixed 105 W limit (70%), set and left, as an operator would;
- **bowl**: Omni through two wires, the clock ceiling (up) and the power limit (down, the lid), pulling the service position (the worse of response time and busy share) to the middle of its bowl; both wires restored to their snapshot at 90% of the run.

## Mean over seeds

| Gauge | Native | Preset | Bowl |
|---|---:|---:|---:|
| work per energy (requests per kJ) | 432.1 | 498.0 | 469.2 |
| energy (J) | 68760 | 59412 | 63337 |
| requests served | 29719 | 29592 | 29719 |
| response, median (ms) | 10.1 | 306.5 | 11.5 |
| response, 95th percentile (ms) | 122.1 | 6942.1 | 124.2 |
| response, 99th percentile (ms) | 602.0 | 8221.0 | 580.8 |
| time over the service line (%) | 2.80% | 40.30% | 2.79% |
| hammer blows per second | 0.95 | 8.39 | 0.85 |
| clock reversals per second | 1.80 | 16.33 | 1.83 |
| clock, mean share of top | 0.984 | 0.777 | 0.814 |
| clock, standard deviation | 0.041 | 0.178 | 0.146 |
| temperature, peak (C) | 75.4 | 64.1 | 74.3 |
| temperature, mean (C) | 66.6 | 61.8 | 63.7 |

## Paired against native (95% interval over seeds)

| Gauge | Preset | Bowl |
|---|---:|---:|
| work per energy | +15.2% (+13.9% to +16.6%) | +8.6% (+7.8% to +9.4%) |
| energy | -13.6% (-14.5% to -12.6%) | -7.9% (-8.6% to -7.2%) |
| time over the line (pp) | +37.50 (+31.22 to +43.79) | -0.01 (-0.06 to +0.03) |
| response p95 | +23419.5% (+8864.0% to +37975.0%) | +32.9% (+6.3% to +59.4%) |
| hammer blows | +831.5% (+674.8% to +988.2%) | -10.5% (-13.6% to -7.4%) |

Both wires back at their snapshot after the kill on every seed: True. Requests served are the same work on every arm (the stream is the seed's); a backlog left at the end is in the JSON.

A model written by the same people who wrote the law is not an independent test. The card's power curve (dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any product. The number that counts is a rented card's own meter.
