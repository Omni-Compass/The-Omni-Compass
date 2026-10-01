# Three columns: Kubernetes alone | Omni-Compass on top | Omni-Compass alone (Omni alone v2, frozen in tuning/C2_PREREGISTRATION.json)

Fresh scenarios 714001-714030 (30 per workload, never used before). THEORETICAL SIMULATION (fleet/sim_slo.py).
Settings frozen before the run. Marks: **better** / *worse* = paired 95% interval vs Kubernetes excludes 0 and the difference is over 0.5%; otherwise equal.

## web

| Gauge | Kubernetes alone | Omni on top | Omni alone |
|---|---:|---:|---:|
| Energy (kWh) | 13.08 | 13.11 (+0%, equal) | 11.8 (-10%, **better**) |
| Machine-hours | 35.46 | 35.46 (+0%, equal) | 28.61 (-19%, **better**) |
| Response time p95 (ms) | 127.3 | 127.2 (-0%, equal) | 121.1 (-5%, **better**) |
| Response time p99 (ms) | 579.4 | 491.3 (-15%, equal) | 145.1 (-75%, **better**) |
| Response time mean (ms) | 204.2 | 204 (-0%, equal) | 148.4 (-27%, **better**) |
| Time over backlog limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Time over power limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Time over heat limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Machine starts+stops | 9.567 | 9.333 (-2%, **better**) | 10 (+5%, equal) |
| Scale reversals | 1.333 | 1.167 (-12%, equal) | 1 (-25%, equal) |
| Pod changes | 618.7 | 618.9 (+0%, equal) | 708.3 (+14%, *worse*) |
| Work completed | 1 | 1 (+0%, equal) | 1 (+0%, equal) |
| Time healthy | 1 | 1 (+0%, equal) | 1 (+0%, equal) |
| Controllers fighting (per day) | 0.3 | 0.2333 (-22%, equal) | 0.03333 (-89%, **better**) |

## multi

| Gauge | Kubernetes alone | Omni on top | Omni alone |
|---|---:|---:|---:|
| Energy (kWh) | 53.93 | 54.05 (+0%, equal) | 49.05 (-9%, **better**) |
| Machine-hours | 145 | 145 (+0%, equal) | 121.5 (-16%, **better**) |
| Response time p95 (ms) | 125 | 125 (-0%, equal) | 119.1 (-5%, **better**) |
| Response time p99 (ms) | 576.3 | 542.7 (-6%, **better**) | 146.9 (-75%, **better**) |
| Response time mean (ms) | 230.5 | 230.2 (-0%, equal) | 155.5 (-33%, **better**) |
| Time over backlog limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Time over power limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Time over heat limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Machine starts+stops | 37.83 | 36.73 (-3%, **better**) | 34.47 (-9%, **better**) |
| Scale reversals | 5.3 | 4.667 (-12%, **better**) | 1.633 (-69%, **better**) |
| Pod changes | 2623 | 2624 (+0%, equal) | 2991 (+14%, *worse*) |
| Work completed | 1 | 1 (+0%, equal) | 1 (+0%, equal) |
| Time healthy | 1 | 1 (+0%, equal) | 1 (+0%, equal) |
| Controllers fighting (per day) | 1.567 | 1.5 (-4%, equal) | 0.1 (-94%, **better**) |

## batch

| Gauge | Kubernetes alone | Omni on top | Omni alone |
|---|---:|---:|---:|
| Energy (kWh) | 63.43 | 62.86 (-1%, **better**) | 59.67 (-6%, **better**) |
| Machine-hours | 92.61 | 90.68 (-2%, **better**) | 76.6 (-17%, **better**) |
| Response time p95 (ms) | 100 | 100 (+0%, equal) | 100 (+0%, equal) |
| Response time p99 (ms) | 1279 | 133.8 (-90%, **better**) | 642.9 (-50%, **better**) |
| Response time mean (ms) | 136.5 | 103.6 (-24%, **better**) | 121.2 (-11%, **better**) |
| Time over backlog limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Time over power limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Time over heat limit | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Machine starts+stops | 13.2 | 10.17 (-23%, **better**) | 12.77 (-3%, equal) |
| Scale reversals | 1.3 | 0.2 (-85%, **better**) | 0.6333 (-51%, **better**) |
| Pod changes | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Work completed | 1 | 1 (+0%, equal) | 1 (+0%, equal) |
| Time healthy | 1 | 1 (+0%, equal) | 1 (+0%, equal) |
| Controllers fighting (per day) | 0 | 0 (+0%, equal) | 0 (+0%, equal) |

## gpu

| Gauge | Kubernetes alone | Omni on top | Omni alone |
|---|---:|---:|---:|
| Energy (kWh) | 198.5 | 198.9 (+0%, equal) | 195.7 (-1%, **better**) |
| Machine-hours | 61.74 | 61.54 (-0%, equal) | 55.16 (-11%, **better**) |
| Response time p95 (ms) | 1.805e+06 | 1.804e+06 (-0%, equal) | 1.803e+06 (-0%, equal) |
| Response time p99 (ms) | 1.912e+06 | 1.91e+06 (-0%, equal) | 1.91e+06 (-0%, equal) |
| Response time mean (ms) | 7.526e+05 | 7.518e+05 (-0%, equal) | 7.516e+05 (-0%, equal) |
| Time over backlog limit | 0.3347 | 0.333 (-0%, equal) | 0.3352 (+0%, equal) |
| Time over power limit | 0.5086 | 0.5086 (+0%, equal) | 0.5005 (-2%, **better**) |
| Time over heat limit | 0.4605 | 0.4613 (+0%, equal) | 0.4552 (-1%, **better**) |
| Machine starts+stops | 16.87 | 11.53 (-32%, **better**) | 14 (-17%, **better**) |
| Scale reversals | 2.867 | 0.9333 (-67%, **better**) | 1 (-65%, **better**) |
| Pod changes | 0 | 0 (+0%, equal) | 0 (+0%, equal) |
| Work completed | 0.9182 | 0.9183 (+0%, equal) | 0.9183 (+0%, equal) |
| Time healthy | 0.4392 | 0.4483 (+2%, **better**) | 0.4532 (+3%, equal) |
| Controllers fighting (per day) | 0.1 | 0.06667 (-33%, equal) | 0.03333 (-67%, equal) |

## Tally across all workloads and gauges

| | better | equal | worse |
|---|---:|---:|---:|
| Omni on top | 13 | 43 | 0 |
| Omni alone | 25 | 29 | 2 |
