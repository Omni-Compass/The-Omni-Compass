# GPU physics simulation: native against Omni-Compass, modelled card

Every number below comes from the card model in tools/gpu_physics_sim.py, not from a meter. It shows what
the governor does to a card that behaves as modelled; the hardware answer is scripts/gpu_paired.sh.

Governor settings: headroom 0.3, min_share 0.7, util_gate 0.5, util_band 0.1, interval 2.0

### Card model gamma 3 (voltage falls with clock)

10 paired repetitions. A change is proven when its 95% interval excludes zero.

| Gauge | Native | Omni | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ | 57.64 | 60.56 | +5.1% | +2.817 to +3.018 |
| GPU energy (J) | 1.005e+05 | 9.568e+04 | -4.8% | -5006 to -4679 |
| GPU mean power (W) | 159.6 | 151.9 | -4.8% | -7.946 to -7.427 |
| requests served | 5794 | 5794 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 97.99 | 102.9 | +5.0% | +4.593 to +5.164 |
| response time, 95th percentile (ms) | 267.5 | 269.8 | +0.9% | +0.9202 to +3.697 |
| response time, 99th percentile (ms) | 420.2 | 420.9 | +0.2% | -0.3945 to +1.821 |
| peak temperature (C) | 61.01 | 61.01 | -0.0% | -0.004555 to -0.0002404 |
| power limit, mean (W) | 300 | 258.8 | -13.7% | -42.19 to -40.24 |
| power-limit writes | 0 | 17.5 | n/a | +14.28 to +20.72 |

Guardrail (preregistered): 95th-percentile response time not above +10%: held (upper bound +1.4%).
**Model verdict: better, proven.**

### Card model gamma 1.5 (near its voltage floor)

10 paired repetitions. A change is proven when its 95% interval excludes zero.

| Gauge | Native | Omni | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ | 57.64 | 58.41 | +1.3% | +0.7487 to +0.7905 |
| GPU energy (J) | 1.005e+05 | 9.92e+04 | -1.3% | -1358 to -1291 |
| GPU mean power (W) | 159.6 | 157.5 | -1.3% | -2.156 to -2.049 |
| requests served | 5794 | 5794 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 97.99 | 107.8 | +10.0% | +9.128 to +10.45 |
| response time, 95th percentile (ms) | 267.5 | 276.1 | +3.2% | +4.467 to +12.61 |
| response time, 99th percentile (ms) | 420.2 | 428.6 | +2.0% | -2.604 to +19.52 |
| peak temperature (C) | 61.01 | 61.01 | -0.0% | -0.001224 to -4.285e-05 |
| power limit, mean (W) | 300 | 264.8 | -11.7% | -36.48 to -33.94 |
| power-limit writes | 0 | 36.1 | n/a | +29.57 to +42.63 |

Guardrail (preregistered): 95th-percentile response time not above +10%: held (upper bound +4.7%).
**Model verdict: better, proven.**

