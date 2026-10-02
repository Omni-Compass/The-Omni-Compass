# GPU bench: native vs Omni-Compass, metered by the device

GPU NVIDIA A10, driver 580.105.08, persistence mode Enabled, start power limit 150.00 W, workload tools/gpu_workload.py (seeded fp16 matmul request stream).
10 repetitions, order rotated, 600.0 s per arm plus 30.0 s drain, 60.0 s idle before each arm.

Phase: **confirm**. Omni frozen at commit c908054053e9; file hashes in FREEZE.json, rechecked at the end.

## Every column, mean over repetitions

| Gauge | Native | Omni watches only | Omni governs |
|---|---:|---:|---:|
| work per energy (served requests per kJ) | 50.79 | 50.85 | 52.62 |
| work per wall energy (served requests per kJ, whole machine) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, whole machine at the wall (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, GPU (J) | 6.918e+04 | 6.911e+04 | 6.679e+04 |
| energy per served request (J) | 19.69 | 19.67 | 19.01 |
| power, GPU mean (W) | 109.5 | 109.4 | 105.7 |
| requests served | 3514 | 3514 | 3514 |
| requests not served | 0 | 0 | 0 |
| response time, mean (ms) | 159.6 | 158.9 | 236.5 |
| response time, 95th percentile (ms) | 510.1 | 507.6 | 808.7 |
| response time, 99th percentile (ms) | 766.6 | 765.5 | 1232 |
| temperature, peak (C) | 75 | 75 | 75 |
| temperature, mean (C) | 63.81 | 63.81 | 62.88 |
| energy, CPU package (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, DRAM (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, platform psys (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, rest of the machine (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, GPU device counter (J) | 6.83e+04 | 6.829e+04 | 6.627e+04 |
| power-capped share of samples | 0.8551 | 0.8553 | 0.7251 |

## Total: Omni governs against native, 10 paired repetitions

| Gauge | Native | Omni governs | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| **work per energy (served requests per kJ) (primary)** | 50.79 | 52.62 | +3.6% | +1.355 to +2.293 | better, proven |
| work per wall energy (served requests per kJ, whole machine) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, whole machine at the wall (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU (J) | 6.918e+04 | 6.679e+04 | -3.5% | -3019 to -1780 | better, proven |
| energy per served request (J) | 19.69 | 19.01 | -3.5% | -0.859 to -0.5066 | better, proven |
| power, GPU mean (W) | 109.5 | 105.7 | -3.5% | -4.781 to -2.822 | better, proven |
| requests served | 3514 | 3514 | +0.0% | +0 to +0 | equal |
| requests not served | 0 | 0 | +0 | +0 to +0 | equal |
| response time, mean (ms) | 159.6 | 236.5 | +48.2% | +65.31 to +88.66 | worse, proven |
| response time, 95th percentile (ms) | 510.1 | 808.7 | +58.5% | +241.8 to +355.2 | worse, proven |
| response time, 99th percentile (ms) | 766.6 | 1232 | +60.8% | +310.6 to +620.9 | worse, proven |
| temperature, peak (C) | 75 | 75 | +0.0% | +0 to +0 | equal |
| temperature, mean (C) | 63.81 | 62.88 | -1.5% | -1.137 to -0.7358 | better, proven |
| energy, CPU package (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, DRAM (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, platform psys (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, rest of the machine (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU device counter (J) | 6.83e+04 | 6.627e+04 | -3.0% | -2249 to -1824 | better, proven |
| power-capped share of samples | 0.8551 | 0.7251 | -15.2% | -0.1372 to -0.1227 | worse, proven |

## Observation: Omni watches only against native, 10 paired repetitions

| Gauge | Native | Omni watches only | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| **work per energy (served requests per kJ) (primary)** | 50.79 | 50.85 | +0.1% | -0.1552 to +0.2699 | better, not proven |
| work per wall energy (served requests per kJ, whole machine) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, whole machine at the wall (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU (J) | 6.918e+04 | 6.911e+04 | -0.1% | -370.3 to +211.8 | better, not proven |
| energy per served request (J) | 19.69 | 19.67 | -0.1% | -0.1054 to +0.06027 | better, not proven |
| power, GPU mean (W) | 109.5 | 109.4 | -0.1% | -0.5873 to +0.3317 | better, not proven |
| requests served | 3514 | 3514 | +0.0% | +0 to +0 | equal |
| requests not served | 0 | 0 | +0 | +0 to +0 | equal |
| response time, mean (ms) | 159.6 | 158.9 | -0.4% | -1.526 to +0.2028 | better, not proven |
| response time, 95th percentile (ms) | 510.1 | 507.6 | -0.5% | -5.841 to +0.815 | better, not proven |
| response time, 99th percentile (ms) | 766.6 | 765.5 | -0.1% | -6.802 to +4.746 | better, not proven |
| temperature, peak (C) | 75 | 75 | +0.0% | +0 to +0 | equal |
| temperature, mean (C) | 63.81 | 63.81 | -0.0% | -0.1897 to +0.1796 | better, not proven |
| energy, CPU package (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, DRAM (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, platform psys (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, rest of the machine (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU device counter (J) | 6.83e+04 | 6.829e+04 | -0.0% | -68.1 to +42.05 | better, not proven |
| power-capped share of samples | 0.8551 | 0.8553 | +0.0% | -0.001697 to +0.002096 | better, not proven |

## Authority: Omni governs against Omni watching, 10 paired repetitions

| Gauge | Omni watches only | Omni governs | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| **work per energy (served requests per kJ) (primary)** | 50.85 | 52.62 | +3.5% | +1.324 to +2.209 | better, proven |
| work per wall energy (served requests per kJ, whole machine) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, whole machine at the wall (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU (J) | 6.911e+04 | 6.679e+04 | -3.4% | -2900 to -1740 | better, proven |
| energy per served request (J) | 19.67 | 19.01 | -3.4% | -0.8252 to -0.4953 | better, proven |
| power, GPU mean (W) | 109.4 | 105.7 | -3.4% | -4.591 to -2.756 | better, proven |
| requests served | 3514 | 3514 | +0.0% | +0 to +0 | equal |
| requests not served | 0 | 0 | +0 | +0 to +0 | equal |
| response time, mean (ms) | 158.9 | 236.5 | +48.9% | +66.2 to +89.1 | worse, proven |
| response time, 95th percentile (ms) | 507.6 | 808.7 | +59.3% | +246.8 to +355.3 | worse, proven |
| response time, 99th percentile (ms) | 765.5 | 1232 | +61.0% | +312.3 to +621.2 | worse, proven |
| temperature, peak (C) | 75 | 75 | +0.0% | +0 to +0 | equal |
| temperature, mean (C) | 63.81 | 62.88 | -1.5% | -1.082 to -0.7809 | better, proven |
| energy, CPU package (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, DRAM (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, platform psys (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, rest of the machine (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU device counter (J) | 6.829e+04 | 6.627e+04 | -3.0% | -2214 to -1833 | better, proven |
| power-capped share of samples | 0.8553 | 0.7251 | -15.2% | -0.1383 to -0.122 | worse, proven |

## Verdict on the preregistered question

Work per energy under Omni against native: 50.79 -> 52.62 served requests per kJ, difference +1.824 (95% interval +1.355 to +2.293).
Guardrails: requests served held (not below -1%), 95th-percentile response time FAILED (not above +10%), requests not served held (not above +1% of native served).
Observation (watch against native) on the same outcome: better, not proven. Authority (omni against watch): better, proven.
**Result, by rule: ENERGY IMPROVEMENT WITH SERVICE TRADEOFF.**

## Actuator fidelity (receipt B: requested against read back from the device)

| Arm | Rep | Writes | Refused | mean abs(read back − requested) W | max W | delay median s | delay max s | enforced under requested | total variation W | reversals | restored |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| omni | 1 | 69 | 0 | 0 | 0 | 0.049 | 0.057 | 18 | 2.37e+03 | 61 | True |
| omni | 2 | 69 | 0 | 0 | 0 | 0.049 | 0.059 | 20 | 2.53e+03 | 57 | True |
| omni | 3 | 91 | 0 | 0 | 0 | 0.049 | 0.06 | 29 | 3.27e+03 | 75 | True |
| omni | 4 | 65 | 0 | 0 | 0 | 0.05 | 0.056 | 25 | 2.45e+03 | 61 | True |
| omni | 5 | 78 | 0 | 0 | 0 | 0.05 | 0.069 | 27 | 2.79e+03 | 67 | True |
| omni | 6 | 93 | 0 | 0 | 0 | 0.05 | 0.06 | 24 | 3.12e+03 | 73 | True |
| omni | 7 | 83 | 0 | 0 | 0 | 0.049 | 0.057 | 27 | 3.17e+03 | 75 | True |
| omni | 8 | 65 | 0 | 0 | 0 | 0.05 | 0.06 | 22 | 2.58e+03 | 61 | True |
| omni | 9 | 61 | 0 | 0 | 0 | 0.05 | 0.059 | 15 | 1.9e+03 | 49 | True |
| omni | 10 | 86 | 0 | 0 | 0 | 0.05 | 0.058 | 26 | 2.92e+03 | 71 | True |
| watch | 1 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 2 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 3 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 4 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 5 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 6 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 7 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 8 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 9 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 10 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |

## Control effort (receipt A)

| Arm | Rep | Decisions | J_u = sum abs(u) dt | mean abs(u) | max abs(u) | saturations | shield interventions | holds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| omni | 1 | 306 | 0 | n/a | n/a | 0 | 306 | 0 |
| omni | 2 | 306 | 0 | n/a | n/a | 0 | 306 | 0 |
| omni | 3 | 305 | 0 | n/a | n/a | 0 | 305 | 0 |
| omni | 4 | 306 | 0 | n/a | n/a | 0 | 306 | 0 |
| omni | 5 | 306 | 0 | n/a | n/a | 0 | 306 | 0 |
| omni | 6 | 305 | 0 | n/a | n/a | 0 | 305 | 0 |
| omni | 7 | 306 | 0 | n/a | n/a | 0 | 306 | 0 |
| omni | 8 | 306 | 0 | n/a | n/a | 0 | 306 | 0 |
| omni | 9 | 306 | 0 | n/a | n/a | 0 | 306 | 0 |
| omni | 10 | 305 | 0 | n/a | n/a | 0 | 305 | 0 |
| watch | 1 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 2 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 3 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 4 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 5 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 6 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 7 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 8 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 9 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |
| watch | 10 | 309 | 0 | n/a | n/a | 0 | 309 | 0 |

## Representation fidelity (the engine's projection against the telemetry at the next decision)

R_int: weighted root-mean-square of h(z next) − F_h(h(z), u) over E, U, I_U, S, B (weights 1). Directional accuracy: the share of movements the projection called in the right direction, movements under 0.01 excluded.

| Arm | Rep | Pairs | R_int | directional accuracy | valid directions | by predicted size |
|---|---|---:|---:|---:|---:|---|
| omni | 1 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 2 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 3 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 4 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 5 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 6 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 7 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 8 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 9 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 10 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 1 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 2 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 3 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 4 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 5 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 6 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 7 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 8 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 9 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 10 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |

## Credit per write (against native at the same moments of the same request stream)

Each write owns the interval until the next write. Joules and requests finished in it, Omni governing minus native; the intervals tile the arm, so the credits add up. The decider is the rule that set the written limit (engine, a floor, the busy gate, a reflex, heat, the speed lock).

| Decided by | Writes | Seconds owned | GPU joules vs native | Requests finished vs native |
|---|---:|---:|---:|---:|
| bowl | 435 | 1676 | -2.394e+04 | -992 |
| fail_up | 317 | 4494 | +1660 | +994 |

## The control

- Writes executed (power limit and clock ceiling): Native 0, Omni watches only 0, Omni governs 2144.
- Every arm ended at the start limit.
- Energy is the device's own power.draw integrated over time; no number here is modelled.
