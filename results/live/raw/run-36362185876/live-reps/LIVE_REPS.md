# Repeated live runs on kind (native vs Omni watching only vs Omni on top vs Omni alone)

## All columns, mean over repetitions

| Gauge | Native | Omni on top |
|---|---:|---:|
| worker nodes in service, mean | 6 | 5.118 |
| node-hours | 1.519 | 1.298 |
| energy (Wh) | 158.7 | 143.9 |
| response time (ms), mean | 91.51 | 60.92 |
| response time (ms), 95th percentile | 201.5 | 92.49 |
| response time (ms), 99th percentile | 297.1 | 110.1 |
| failed requests (%) | 0 | 0 |
| pending pods, pod-minutes | 0.2633 | 0.16 |
| utilisation (used / allocatable) | 0.0348 | 0.04832 |
| CPU used (cores), mean | 0.8351 | 0.9923 |
| energy per core-hour (Wh) | 754.6 | 578.8 |
| HPA replicas, mean | 8.726 | 5.49 |

## B: Omni-Compass on top vs native, 5 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.118 | -14.7% | -1.251 to -0.514 | yes, better |
| node-hours | 1.519 | 1.298 | -14.5% | -0.3156 to -0.1254 | yes, better |
| energy (Wh) | 158.7 | 143.9 | -9.3% | -22.87 to -6.793 | yes, better |
| response time (ms), mean | 91.51 | 60.92 | -33.4% | -55.51 to -5.661 | yes, better |
| response time (ms), 95th percentile | 201.5 | 92.49 | -54.1% | -147.8 to -70.16 | yes, better |
| response time (ms), 99th percentile | 297.1 | 110.1 | -63.0% | -237.5 to -136.6 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.2633 | 0.16 | -39.2% | -0.6034 to +0.3968 | no |
| utilisation (used / allocatable) | 0.0348 | 0.04832 | +38.9% | +0.01034 to +0.01672 | yes, better |
| CPU used (cores), mean | 0.8351 | 0.9923 | +18.8% | +0.05349 to +0.2608 | yes, better |
| energy per core-hour (Wh) | 754.6 | 578.8 | -23.3% | -197.2 to -154.4 | yes, better |
| HPA replicas, mean | 8.726 | 5.49 | -37.1% | -4.044 to -2.428 | yes, better |
