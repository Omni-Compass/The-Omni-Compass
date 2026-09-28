# GPU physics simulation: native against Omni-Compass, modelled card

Every number below comes from the card model in tools/gpu_physics_sim.py, not from a meter. It shows what
the governor does to a card that behaves as modelled; the hardware answer is scripts/gpu_paired.sh.

Governor settings: headroom 0.3, min_share 0.75, util_gate 0.5, util_band 0.1, interval 5.0

### Card model gamma 3 (voltage falls with clock)

10 paired repetitions. A change is proven when its 95% interval excludes zero.

| Gauge | Native | Omni | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ | 57.64 | 59.99 | +4.1% | +2.236 to +2.462 |
| GPU energy (J) | 1.005e+05 | 9.659e+04 | -3.9% | -4118 to -3754 |
| GPU mean power (W) | 159.6 | 153.3 | -3.9% | -6.537 to -5.958 |
| requests served | 5794 | 5794 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 97.99 | 102 | +4.1% | +3.578 to +4.489 |
| response time, 95th percentile (ms) | 267.5 | 271.1 | +1.3% | +0.3282 to +6.727 |
| response time, 99th percentile (ms) | 420.2 | 421.7 | +0.4% | -0.2941 to +3.367 |
| peak temperature (C) | 61.01 | 61.01 | -0.0% | -0.001652 to -0.0005261 |
| power limit, mean (W) | 300 | 266.9 | -11.0% | -34.18 to -32.07 |
| power-limit writes | 0 | 7.4 | n/a | +6.709 to +8.091 |

Guardrail (preregistered): 95th-percentile response time not above +10%: held (upper bound +2.5%).
**Model verdict: better, proven.**

### Card model gamma 1.5 (near its voltage floor)

10 paired repetitions. A change is proven when its 95% interval excludes zero.

| Gauge | Native | Omni | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ | 57.64 | 58.32 | +1.2% | +0.6357 to +0.7208 |
| GPU energy (J) | 1.005e+05 | 9.935e+04 | -1.2% | -1241 to -1097 |
| GPU mean power (W) | 159.6 | 157.7 | -1.2% | -1.969 to -1.742 |
| requests served | 5794 | 5794 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 97.99 | 106.5 | +8.7% | +7.192 to +9.877 |
| response time, 95th percentile (ms) | 267.5 | 278.5 | +4.1% | +3.58 to +18.29 |
| response time, 99th percentile (ms) | 420.2 | 440.7 | +4.9% | -3.728 to +44.79 |
| peak temperature (C) | 61.01 | 61.01 | -0.0% | -0.0003875 to -9.664e-05 |
| power limit, mean (W) | 300 | 270 | -10.0% | -31.53 to -28.47 |
| power-limit writes | 0 | 12.2 | n/a | +9.918 to +14.48 |

Guardrail (preregistered): 95th-percentile response time not above +10%: held (upper bound +6.8%).
**Model verdict: better, proven.**

