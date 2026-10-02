# The two-wire GPU card, in simulation

Evidence class **S** (a model, not a meter). Seeds 5000-5009, 600 s each, commit `05eab70`, 2026-10-02 22:04 UTC. Model and arms: `realms/gpu_card.py`; the law: `omnicompass/bowl.py`. The frozen engine is not used here; this is the bowl law as its own arm.

- **native**: the card as shipped, 150 W limit, firmware boost up a bin and hammer down three at the limit;
- **preset**: a fixed 105 W limit (70%), set and left, as an operator would;
- **old governor**: the shipped one-wire GPU governor (its defaults), the power limit only;
- **bowl**: Omni through two wires, the clock ceiling (up) and the power limit (down, the lid), pulling the service position (response time) to the middle of its bowl, racing at full speed while the card is saturated and never pacing under the clock or the draw the card reaches on its own while busy (amendment 6); both wires restored to their snapshot at 90% of the run. **Service** profile (the default and the benchmark's arm): down gain 0.0125, bowl center 0.4, speed floor 3% above the card's own busy clock; **batch** profile: down gain 0.015, center 0.5, floor at the card's own busy clock, for work nobody waits on answer by answer.

## Mean over seeds

| Gauge | Native | Preset | Old governor | Bowl, service | Bowl, batch |
|---|---:|---:|---:|---:|---:|
| work per energy (requests per kJ) | 432.1 | 498.0 | 432.3 | 461.8 | 467.4 |
| energy (J) | 68760 | 59412 | 68725 | 64371 | 63622 |
| requests served | 29719 | 29592 | 29719 | 29719 | 29719 |
| response, median (ms) | 10.1 | 306.5 | 10.1 | 11.9 | 12.1 |
| response, 95th percentile (ms) | 122.1 | 6942.1 | 122.2 | 118.7 | 123.4 |
| response, 99th percentile (ms) | 602.0 | 8221.0 | 602.0 | 582.0 | 587.5 |
| time over the service line (%) | 2.80% | 40.30% | 2.80% | 2.78% | 2.86% |
| hammer blows per second | 0.95 | 8.39 | 1.03 | 0.67 | 0.65 |
| clock reversals per second | 1.80 | 16.33 | 1.94 | 1.30 | 1.29 |
| clock, mean share of top | 0.984 | 0.777 | 0.983 | 0.867 | 0.844 |
| clock, standard deviation | 0.041 | 0.178 | 0.043 | 0.060 | 0.080 |
| temperature, peak (C) | 75.4 | 64.1 | 75.4 | 73.7 | 73.6 |
| temperature, mean (C) | 66.6 | 61.8 | 66.6 | 64.2 | 63.8 |

## Paired against native (ratios: geometric mean over seeds with its 95% interval; time over the line: mean difference)

| Gauge | Preset | Old governor | Bowl, service | Bowl, batch |
|---|---:|---:|---:|---:|
| work per energy | +15.2% (+13.9% to +16.6%) | +0.1% (+0.0% to +0.1%) | +6.9% (+5.4% to +8.3%) | +8.1% (+6.2% to +10.1%) |
| energy | -13.6% (-14.5% to -12.6%) | -0.1% (-0.1% to -0.0%) | -6.4% (-7.7% to -5.1%) | -7.5% (-9.1% to -5.9%) |
| time over the line (pp) | +37.50 (+31.22 to +43.79) | +0.00 (+0.00 to +0.00) | -0.03 (-0.05 to +0.00) | +0.06 (-0.06 to +0.18) |
| response p95 | +13233.8% (+5341.2% to +32575.1%) | +0.8% (-1.0% to +2.5%) | -5.9% (-15.3% to +4.5%) | +7.0% (-4.8% to +20.3%) |
| hammer blows | +809.3% (+671.2% to +972.2%) | +9.0% (+6.5% to +11.5%) | -31.5% (-44.0% to -16.2%) | -32.1% (-42.9% to -19.2%) |

Both wires back at their snapshot after the kill on every seed: True. Requests served are the same work on every arm (the stream is the seed's); a backlog left at the end is in the JSON.

A model written by the same people who wrote the law is not an independent test. The card's power curve (dynamic power rising with clock times voltage squared) is the textbook shape, not a measurement of any product. The number that counts is a rented card's own meter.
