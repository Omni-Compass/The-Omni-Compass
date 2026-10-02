# GPU bench: native vs Omni-Compass, metered by the device

GPU NVIDIA A10, driver 580.105.08, persistence mode Enabled, start power limit 150.00 W, workload tools/gpu_workload.py (seeded fp16 matmul request stream).
3 repetitions, order rotated, 180.0 s per arm plus 30.0 s drain, 30.0 s idle before each arm.

Phase: **smoke**. Omni frozen at commit c908054053e9; file hashes in FREEZE.json, rechecked at the end.

## Every column, mean over repetitions

| Gauge | Native | Omni watches only | Omni governs |
|---|---:|---:|---:|
| work per energy (served requests per kJ) | 50.9 | 50.82 | 51.38 |
| work per wall energy (served requests per kJ, whole machine) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, whole machine at the wall (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, GPU (J) | 2.23e+04 | 2.233e+04 | 2.209e+04 |
| energy per served request (J) | 19.65 | 19.68 | 19.46 |
| power, GPU mean (W) | 105.3 | 105.5 | 104.3 |
| requests served | 1135 | 1135 | 1135 |
| requests not served | 0 | 0 | 0 |
| response time, mean (ms) | 192.1 | 199.7 | 355.9 |
| response time, 95th percentile (ms) | 723.6 | 772.6 | 1537 |
| response time, 99th percentile (ms) | 903.8 | 943.7 | 1816 |
| temperature, peak (C) | 67.33 | 67.67 | 67.33 |
| temperature, mean (C) | 60.38 | 61.36 | 61.1 |
| energy, CPU package (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, DRAM (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, platform psys (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, rest of the machine (J) | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| energy, GPU device counter (J) | 2.215e+04 | 2.222e+04 | 2.188e+04 |
| power-capped share of samples | 0.7863 | 0.7835 | 0.7179 |

## Total: Omni governs against native, 3 paired repetitions

| Gauge | Native | Omni governs | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| **work per energy (served requests per kJ) (primary)** | 50.9 | 51.38 | +0.9% | -0.6565 to +1.606 | better, not proven |
| work per wall energy (served requests per kJ, whole machine) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, whole machine at the wall (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU (J) | 2.23e+04 | 2.209e+04 | -0.9% | -702 to +288.4 | better, not proven |
| energy per served request (J) | 19.65 | 19.46 | -0.9% | -0.6185 to +0.2541 | better, not proven |
| power, GPU mean (W) | 105.3 | 104.3 | -1.0% | -3.494 to +1.469 | better, not proven |
| requests served | 1135 | 1135 | +0.0% | +0 to +0 | equal |
| requests not served | 0 | 0 | +0 | +0 to +0 | equal |
| response time, mean (ms) | 192.1 | 355.9 | +85.2% | -15.43 to +342.9 | worse, not proven |
| response time, 95th percentile (ms) | 723.6 | 1537 | +112.4% | -508 to +2135 | worse, not proven |
| response time, 99th percentile (ms) | 903.8 | 1816 | +100.9% | -54.81 to +1879 | worse, not proven |
| temperature, peak (C) | 67.33 | 67.33 | +0.0% | -2.484 to +2.484 | worse, not proven |
| temperature, mean (C) | 60.38 | 61.1 | +1.2% | -4.04 to +5.466 | worse, not proven |
| energy, CPU package (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, DRAM (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, platform psys (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, rest of the machine (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU device counter (J) | 2.215e+04 | 2.188e+04 | -1.2% | -725.8 to +193.3 | better, not proven |
| power-capped share of samples | 0.7863 | 0.7179 | -8.7% | -0.0723 to -0.06452 | worse, proven |

## Observation: Omni watches only against native, 3 paired repetitions

| Gauge | Native | Omni watches only | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| **work per energy (served requests per kJ) (primary)** | 50.9 | 50.82 | -0.2% | -1.126 to +0.9648 | worse, not proven |
| work per wall energy (served requests per kJ, whole machine) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, whole machine at the wall (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU (J) | 2.23e+04 | 2.233e+04 | +0.2% | -418.9 to +491.3 | worse, not proven |
| energy per served request (J) | 19.65 | 19.68 | +0.2% | -0.3691 to +0.4329 | worse, not proven |
| power, GPU mean (W) | 105.3 | 105.5 | +0.2% | -1.975 to +2.316 | worse, not proven |
| requests served | 1135 | 1135 | +0.0% | +0 to +0 | equal |
| requests not served | 0 | 0 | +0 | +0 to +0 | equal |
| response time, mean (ms) | 192.1 | 199.7 | +3.9% | -22.34 to +37.45 | worse, not proven |
| response time, 95th percentile (ms) | 723.6 | 772.6 | +6.8% | -136 to +234 | worse, not proven |
| response time, 99th percentile (ms) | 903.8 | 943.7 | +4.4% | -101.8 to +181.6 | worse, not proven |
| temperature, peak (C) | 67.33 | 67.67 | +0.5% | -1.101 to +1.768 | worse, not proven |
| temperature, mean (C) | 60.38 | 61.36 | +1.6% | -3.386 to +5.33 | worse, not proven |
| energy, CPU package (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, DRAM (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, platform psys (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, rest of the machine (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU device counter (J) | 2.215e+04 | 2.222e+04 | +0.3% | -322.9 to +462.2 | worse, not proven |
| power-capped share of samples | 0.7863 | 0.7835 | -0.4% | -0.01594 to +0.01026 | worse, not proven |

## Authority: Omni governs against Omni watching, 3 paired repetitions

| Gauge | Omni watches only | Omni governs | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| **work per energy (served requests per kJ) (primary)** | 50.82 | 51.38 | +1.1% | -1.11 to +2.222 | better, not proven |
| work per wall energy (served requests per kJ, whole machine) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, whole machine at the wall (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU (J) | 2.233e+04 | 2.209e+04 | -1.1% | -970.8 to +484.8 | better, not proven |
| energy per served request (J) | 19.68 | 19.46 | -1.1% | -0.8553 to +0.4272 | better, not proven |
| power, GPU mean (W) | 105.5 | 104.3 | -1.1% | -4.736 to +2.37 | better, not proven |
| requests served | 1135 | 1135 | +0.0% | +0 to +0 | equal |
| requests not served | 0 | 0 | +0 | +0 to +0 | equal |
| response time, mean (ms) | 199.7 | 355.9 | +78.2% | -19.99 to +332.3 | worse, not proven |
| response time, 95th percentile (ms) | 772.6 | 1537 | +99.0% | -473.2 to +2002 | worse, not proven |
| response time, 99th percentile (ms) | 943.7 | 1816 | +92.4% | -33.36 to +1778 | worse, not proven |
| temperature, peak (C) | 67.67 | 67.33 | -0.5% | -1.768 to +1.101 | better, not proven |
| temperature, mean (C) | 61.36 | 61.1 | -0.4% | -0.7098 to +0.1927 | better, not proven |
| energy, CPU package (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, DRAM (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, platform psys (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, rest of the machine (J) | UNAVAILABLE | UNAVAILABLE | | | no meter |
| energy, GPU device counter (J) | 2.222e+04 | 2.188e+04 | -1.5% | -402.9 to -268.9 | better, proven |
| power-capped share of samples | 0.7835 | 0.7179 | -8.4% | -0.07621 to -0.05493 | worse, proven |

## Verdict on the preregistered question

Work per energy under Omni against native: 50.9 -> 51.38 served requests per kJ, difference +0.4749 (95% interval -0.6565 to +1.606).
Guardrails: requests served held (not below -1%), 95th-percentile response time FAILED (not above +10%), requests not served held (not above +1% of native served).
Observation (watch against native) on the same outcome: worse, not proven. Authority (omni against watch): better, not proven.
**Result, by rule: NOT ESTABLISHED.**

## Actuator fidelity (receipt B: requested against read back from the device)

| Arm | Rep | Writes | Refused | mean abs(read back − requested) W | max W | delay median s | delay max s | enforced under requested | total variation W | reversals | restored |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| omni | 1 | 16 | 0 | 0 | 0 | 0.049 | 0.059 | 4 | 552 | 13 | True |
| omni | 2 | 21 | 0 | 0 | 0 | 0.05 | 0.059 | 7 | 852 | 19 | True |
| omni | 3 | 24 | 0 | 0 | 0 | 0.049 | 0.057 | 4 | 774 | 19 | True |
| watch | 1 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 2 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |
| watch | 3 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | 0 | True |

## Control effort (receipt A)

| Arm | Rep | Decisions | J_u = sum abs(u) dt | mean abs(u) | max abs(u) | saturations | shield interventions | holds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| omni | 1 | 103 | 0 | n/a | n/a | 0 | 103 | 0 |
| omni | 2 | 103 | 0 | n/a | n/a | 0 | 103 | 0 |
| omni | 3 | 103 | 0 | n/a | n/a | 0 | 103 | 0 |
| watch | 1 | 104 | 0 | n/a | n/a | 0 | 104 | 0 |
| watch | 2 | 104 | 0 | n/a | n/a | 0 | 104 | 0 |
| watch | 3 | 104 | 0 | n/a | n/a | 0 | 104 | 0 |

## Representation fidelity (the engine's projection against the telemetry at the next decision)

R_int: weighted root-mean-square of h(z next) − F_h(h(z), u) over E, U, I_U, S, B (weights 1). Directional accuracy: the share of movements the projection called in the right direction, movements under 0.01 excluded.

| Arm | Rep | Pairs | R_int | directional accuracy | valid directions | by predicted size |
|---|---|---:|---:|---:|---:|---|
| omni | 1 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 2 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| omni | 3 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 1 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 2 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |
| watch | 3 | 0 | n/a | n/a | 0 | 0.01-0.03: n/a of 0, 0.03-0.1: n/a of 0, >=0.1: n/a of 0 |

## Credit per write (against native at the same moments of the same request stream)

Each write owns the interval until the next write. Joules and requests finished in it, Omni governing minus native; the intervals tile the arm, so the credits add up. The decider is the rule that set the written limit (engine, a floor, the busy gate, a reflex, heat, the speed lock).

| Decided by | Writes | Seconds owned | GPU joules vs native | Requests finished vs native |
|---|---:|---:|---:|---:|
| bowl | 34 | 99 | -1418 | -105 |
| fail_up | 25 | 472 | +946.3 | +106 |

## The control

- Writes executed (power limit and clock ceiling): Native 0, Omni watches only 0, Omni governs 183.
- Every arm ended at the start limit.
- Energy is the device's own power.draw integrated over time; no number here is modelled.
