# Speed won on the CPU, spent on the GPU (model)

CPU work 20 ms per request; pod CPU limit 0.5 core native, 1 conveyed. GPU as tools/gpu_physics_sim.py. Baseline from 3 native runs on other seeds.
Lock settings: speed_gain 0.01, lock_margin 0.08, lock_step 0.02, lock_window_s 60.0, lock_floor 0.5, interval 2.0
Every number comes from the model in this file and tools/gpu_physics_sim.py, not from a meter.

### Card model gamma 3, 5 paired repetitions

#### CPU muscle only (speed handed to the customer)

| Gauge | Native | This arm | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ (GPU) | 57.66 | 57.66 | +0.0% | +0 to +0 |
| GPU energy (J) | 1.007e+05 | 1.007e+05 | +0.0% | +0 to +0 |
| requests served | 5804 | 5804 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 114.4 | 114.4 | +0.0% | +0 to +0 |
| response time, 95th percentile (ms) | 268.1 | 268.1 | +0.0% | +0 to +0 |
| response time, 99th percentile (ms) | 409.6 | 409.6 | +0.0% | +0 to +0 |
| GPU power limit, mean (W) | 300 | 300 | +0.0% | +0 to +0 |
| power-limit writes | 0 | 0 | n/a | +0 to +0 |

#### CPU muscle + GPU speed lock (speed spent on watts)

| Gauge | Native | This arm | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ (GPU) | 57.66 | 57.79 | +0.2% | -0.0131 to +0.2608 |
| GPU energy (J) | 1.007e+05 | 1.004e+05 | -0.2% | -454.4 to +22.57 |
| requests served | 5804 | 5804 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 114.4 | 116.3 | +1.6% | +0.8112 to +2.874 |
| response time, 95th percentile (ms) | 268.1 | 277.5 | +3.5% | +2.505 to +16.33 |
| response time, 99th percentile (ms) | 409.6 | 430.2 | +5.0% | -1.627 to +42.82 |
| GPU power limit, mean (W) | 300 | 298.7 | -0.4% | -2.349 to -0.2192 |
| power-limit writes | 0 | 8.8 | n/a | +4.645 to +12.95 |

Speed lock (every gauge at least 1% faster than native, upper end of its 95% interval): mean +2.5%, 95th percentile +6.1%, 99th percentile +10.5% -> **NOT HELD**.

