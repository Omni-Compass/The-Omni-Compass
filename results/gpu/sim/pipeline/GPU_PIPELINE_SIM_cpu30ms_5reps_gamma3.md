# Speed won on the CPU, spent on the GPU (model)

CPU work 30 ms per request; pod CPU limit 0.5 core native, 1 conveyed. GPU as tools/gpu_physics_sim.py. Baseline from 3 native runs on other seeds.
Lock settings: speed_gain 0.01, lock_margin 0.08, lock_step 0.02, lock_window_s 60.0, lock_floor 0.5, interval 2.0
Every number comes from the model in this file and tools/gpu_physics_sim.py, not from a meter.

### Card model gamma 3, 5 paired repetitions

#### CPU muscle only (speed handed to the customer)

| Gauge | Native | This arm | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ (GPU) | 57.66 | 57.66 | +0.0% | +6.44e-15 to +9.588e-14 |
| GPU energy (J) | 1.007e+05 | 1.007e+05 | -0.0% | -1.694e-10 to -1.106e-11 |
| requests served | 5804 | 5804 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 250.4 | 124.4 | -50.3% | -209.3 to -42.68 |
| response time, 95th percentile (ms) | 913.2 | 278.1 | -69.5% | -1070 to -200.3 |
| response time, 99th percentile (ms) | 1360 | 419.6 | -69.1% | -1707 to -173 |
| GPU power limit, mean (W) | 300 | 300 | +0.0% | +0 to +0 |
| power-limit writes | 0 | 0 | n/a | +0 to +0 |

#### CPU muscle + GPU speed lock (speed spent on watts)

| Gauge | Native | This arm | Change | 95% interval of the difference |
|---|---:|---:|---:|---:|
| requests served per kJ (GPU) | 57.66 | 60.07 | +4.2% | +1.843 to +2.971 |
| GPU energy (J) | 1.007e+05 | 9.663e+04 | -4.0% | -4954 to -3104 |
| requests served | 5804 | 5804 | +0.0% | +0 to +0 |
| requests not served | 0 | 0 | n/a | +0 to +0 |
| response time, mean (ms) | 250.4 | 143.5 | -42.7% | -186.8 to -27.02 |
| response time, 95th percentile (ms) | 913.2 | 355.5 | -61.1% | -985.7 to -129.7 |
| response time, 99th percentile (ms) | 1360 | 591.9 | -56.5% | -1468 to -67.19 |
| GPU power limit, mean (W) | 300 | 279.3 | -6.9% | -25.82 to -15.56 |
| power-limit writes | 0 | 30.8 | n/a | +28.41 to +33.19 |

Speed lock (every gauge at least 1% faster than native, upper end of its 95% interval): mean -10.8%, 95th percentile -14.2%, 99th percentile -4.9% -> **HELD**.

