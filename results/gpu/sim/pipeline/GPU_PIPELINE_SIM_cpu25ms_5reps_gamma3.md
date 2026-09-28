# Speed won on the CPU, spent on the GPU (model)

CPU work 25 ms per request; pod CPU limit 0.5 core native, 1 conveyed. GPU as tools/gpu_physics_sim.py. Baseline from 3 native runs on other seeds.
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
| response time, mean (ms) | 119.4 | 119.4 | +0.0% | +0 to +0 |
| response time, 95th percentile (ms) | 273.1 | 273.1 | +0.0% | +0 to +0 |
| response time, 99th percentile (ms) | 414.6 | 414.6 | +0.0% | +0 to +0 |
| GPU power limit, mean (W) | 300 | 300 | +0.0% | +0 to +0 |
| power-limit writes | 0 | 0 | n/a | +0 to +0 |

#### CPU muscle + GPU speed lock (speed spent on watts)

| Gauge | Native | This arm | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ (GPU) | 57.66 | 57.78 | +0.2% | -0.01614 to +0.2567 |
| GPU energy (J) | 1.007e+05 | 1.004e+05 | -0.2% | -447.3 to +27.81 |
| requests served | 5804 | 5804 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 119.4 | 121.3 | +1.5% | +0.7535 to +2.92 |
| response time, 95th percentile (ms) | 273.1 | 282.5 | +3.5% | +2.477 to +16.49 |
| response time, 99th percentile (ms) | 414.6 | 433.9 | +4.7% | -3.12 to +41.75 |
| GPU power limit, mean (W) | 300 | 298.8 | -0.4% | -2.3 to -0.1643 |
| power-limit writes | 0 | 8.2 | n/a | +4.045 to +12.35 |

Speed lock (every gauge at least 1% faster than native, upper end of its 95% interval): mean +2.4%, 95th percentile +6.0%, 99th percentile +10.1% -> **NOT HELD**.

