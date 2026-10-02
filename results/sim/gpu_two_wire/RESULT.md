# The two-wire GPU card, in simulation

Evidence class **S** (a model, not a meter). Seeds 5000-5009, 600 s each, commit `da5da18`, 2026-10-02 21:00 UTC. Model and arms: `realms/gpu_card.py`; the law: `omnicompass/bowl.py`. The frozen engine is not used here; this is the bowl law as its own arm.

- **native**: the card as shipped, 150 W limit, firmware boost up a bin and hammer down three at the limit;
- **preset**: a fixed 105 W limit (70%), set and left, as an operator would;
- **old governor**: the shipped one-wire GPU governor (its defaults), the power limit only;
- **bowl**: Omni through two wires, the clock ceiling (up) and the power limit (down, the lid), pulling the service position (response time) to the middle of its bowl, racing at full speed while the card is saturated and never pacing under the clock or the draw the card reaches on its own while busy (amendment 6); both wires restored to their snapshot at 90% of the run.

## Mean over seeds

| Gauge | Native | Preset | Old governor | Bowl |
|---|---:|---:|---:|---:|
| work per energy (requests per kJ) | 432.1 | 498.0 | 432.3 | 467.5 |
| energy (J) | 68760 | 59412 | 68725 | 63605 |
| requests served | 29719 | 29592 | 29719 | 29719 |
| response, median (ms) | 10.1 | 306.5 | 10.1 | 12.1 |
| response, 95th percentile (ms) | 122.1 | 6942.1 | 122.2 | 123.7 |
| response, 99th percentile (ms) | 602.0 | 8221.0 | 602.0 | 587.6 |
| time over the service line (%) | 2.80% | 40.30% | 2.80% | 2.86% |
| hammer blows per second | 0.95 | 8.39 | 1.03 | 0.65 |
| clock reversals per second | 1.80 | 16.33 | 1.94 | 1.28 |
| clock, mean share of top | 0.984 | 0.777 | 0.983 | 0.844 |
| clock, standard deviation | 0.041 | 0.178 | 0.043 | 0.079 |
| temperature, peak (C) | 75.4 | 64.1 | 75.4 | 73.5 |
| temperature, mean (C) | 66.6 | 61.8 | 66.6 | 63.8 |

## Paired against native (95% interval over seeds)

| Gauge | Preset | Old governor | Bowl |
|---|---:|---:|---:|
| work per energy | +15.2% (+13.9% to +16.6%) | +0.1% (+0.0% to +0.1%) | +8.2% (+6.3% to +10.1%) |
| energy | -13.6% (-14.5% to -12.6%) | -0.1% (-0.1% to -0.0%) | -7.5% (-9.2% to -5.9%) |
| time over the line (pp) | +37.50 (+31.22 to +43.79) | +0.00 (+0.00 to +0.00) | +0.06 (-0.05 to +0.18) |
| response p95 | +23419.5% (+8864.0% to +37975.0%) | +0.8% (-1.0% to +2.6%) | +9.4% (-4.0% to +22.8%) |
| hammer blows | +831.5% (+674.8% to +988.2%) | +9.0% (+6.5% to +11.6%) | -30.5% (-42.5% to -18.4%) |

Both wires back at their snapshot after the kill on every seed: True. Requests served are the same work on every arm (the stream is the seed's); a backlog left at the end is in the JSON.

A model written by the same people who wrote the law is not an independent test. The card's power curve (dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any product. The number that counts is a rented card's own meter.
