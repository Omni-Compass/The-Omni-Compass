# GPU physics simulation: native against Omni-Compass, modelled card

Every number below comes from the card model in tools/gpu_physics_sim.py, not from a meter. It shows what
the governor does to a card that behaves as modelled; the hardware answer is scripts/gpu_paired.sh.

Governor settings: headroom 0.3, min_share 0.0, util_gate 0.0, util_band 0.1, interval 5.0

### Card model gamma 3 (voltage falls with clock)

10 paired repetitions. A change is proven when its 95% interval excludes zero.

| Gauge | Native | Omni | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ | 57.64 | 65.07 | +12.9% | +7.081 to +7.789 |
| GPU energy (J) | 1.005e+05 | 8.905e+04 | -11.4% | -1.192e+04 to -1.104e+04 |
| GPU mean power (W) | 159.6 | 141.3 | -11.4% | -18.92 to -17.52 |
| requests served | 5794 | 5794 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 97.99 | 126.3 | +28.9% | +25.46 to +31.19 |
| response time, 95th percentile (ms) | 267.5 | 349.7 | +30.7% | +66.43 to +97.96 |
| response time, 99th percentile (ms) | 420.2 | 564.6 | +34.4% | +95.8 to +193.2 |
| peak temperature (C) | 61.01 | 60.46 | -0.9% | -0.7666 to -0.3203 |
| power limit, mean (W) | 300 | 227.3 | -24.2% | -75.52 to -69.92 |
| power-limit writes | 0 | 42.3 | n/a | +38.71 to +45.89 |

Guardrail (preregistered): 95th-percentile response time not above +10%: FAILED (upper bound +36.6%).
**Model verdict: better on energy, fails the service guardrail.**

### Card model gamma 1.5 (near its voltage floor)

10 paired repetitions. A change is proven when its 95% interval excludes zero.

| Gauge | Native | Omni | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ | 57.64 | 59.16 | +2.6% | +1.405 to +1.648 |
| GPU energy (J) | 1.005e+05 | 9.793e+04 | -2.6% | -2790 to -2394 |
| GPU mean power (W) | 159.6 | 155.4 | -2.6% | -4.429 to -3.8 |
| requests served | 5794 | 5794 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 97.99 | 149.5 | +52.6% | +42.76 to +60.3 |
| response time, 95th percentile (ms) | 267.5 | 444.1 | +66.0% | +125 to +228.2 |
| response time, 99th percentile (ms) | 420.2 | 777.8 | +85.1% | +240.5 to +474.7 |
| peak temperature (C) | 61.01 | 60.93 | -0.1% | -0.1504 to -0.004961 |
| power limit, mean (W) | 300 | 242.5 | -19.2% | -61.31 to -53.61 |
| power-limit writes | 0 | 41.4 | n/a | +36.36 to +46.44 |

Guardrail (preregistered): 95th-percentile response time not above +10%: FAILED (upper bound +85.3%).
**Model verdict: better on energy, fails the service guardrail.**

