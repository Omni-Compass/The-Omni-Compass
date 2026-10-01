# What the runs showed

## Mechanism on recorded CPU percent

File: `fixtures/METRICS_SERVER_CAPTURE.csv`
51,840 rows. 9 PlanetLab traces. 15 s hold-last.
`cluster_desired_replicas` = independent HPA v2 algorithm on that metric. Not an apiserver.

| Check | Result |
|---|---|
| Two HPA implementations agree | 51840/51840 |
| Omni observe leaves HPA path unchanged | 9/9 |
| Finite engine state | 51840/51840 |
| Push bounded | 51840/51840 |
| S ≥ S− | 51840/51840 |
| Shield hits on raw directives | 73/51840 |
| Mean recorded metric | 0.086 |
| Omni ρ* | 0.832–0.914 |
| HPA replica changes / 24 h trace | 0.89 |

## Open-loop replay of the same series

| Arm | Energy kWh | Scale-up | Scale-down |
|---|---|---|---|
| HPA 0.70 | 14.47 | 0.0 | 1.3 |
| Omni observe | 14.47 | 0.0 | 1.3 |
| Omni writes target | 14.47 | 0.0 | 1.3 |
| HPA 0.50 | 21.24 | 14.9 | 7.9 |

Closed-loop plant on these traces saturated. Numbers from that mode are unused.

## 15 s synthetic plant (24 scenarios)

Observe identity vs HPA+CA: 24/24.

| Arm | Energy kWh | Healthy | Starts / stops |
|---|---|---|---|
| hpa70_ca | 168.83 | 93.0% | 21.5 / 12.9 |
| omni_observe_hpa70_ca | 168.83 | 93.0% | 21.5 / 12.9 |
| omni_target_hpa70_ca | 162.03 | 92.9% | 23.8 / 21.1 |
| omni_target_down_hpa70_ca before fix | 171.88 | 81.1% | 88.0 / 83.8 |
| omni_target_down after fix | 185.53 | 84.7% | 20.0 / 7.1 |
| omni_target ρ0=0.95 | 160.49 | 93.0% | 23.4 / 21.5 |
| omni_target_gate ρ0=0.95 | 154.10 | 93.2% | 26.4 / 24.8 |

Gate vs HPA+CA on 24 scenarios: 168.83 → 154.10 kWh (−8.7%), health 93.0% → 93.2%, availability 1.0.
Writes HPA target = ρ*. When push is released and queue is low, CA unneeded/delay-after-add shorten. No Omni node yank.
