# Repeated live runs on kind (native vs Omni watching only vs Omni on top vs Omni alone)

## All columns, mean over repetitions

| Gauge | Native | Omni on top |
|---|---:|---:|
| worker nodes in service, mean | 6 | 4.959 |
| node-hours | 1.515 | 1.251 |
| energy (Wh) | 158.7 | 141.2 |
| response time (ms), mean | 126.1 | 79.36 |
| response time (ms), 95th percentile | 264 | 120 |
| response time (ms), 99th percentile | 374.9 | 154.4 |
| failed requests (%) | 0 | 0 |
| pending pods, pod-minutes | 0.3667 | 0.2333 |
| utilisation (used / allocatable) | 0.03669 | 0.05626 |
| CPU used (cores), mean | 0.8806 | 1.112 |
| energy per core-hour (Wh) | 716.1 | 509.4 |
| HPA replicas, mean | 8.816 | 6.565 |
| pods started | 4.9 | 2.6 |
| pod start wait, total (s) | 13.8 | 7.1 |
| pod start wait, mean (s) | 2.733 | 1.477 |

## B: Omni-Compass on top vs native, 10 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.959 | -17.4% | -1.349 to -0.7333 | yes, better |
| node-hours | 1.515 | 1.251 | -17.4% | -0.3425 to -0.1858 | yes, better |
| energy (Wh) | 158.7 | 141.2 | -11.0% | -23.57 to -11.47 | yes, better |
| response time (ms), mean | 126.1 | 79.36 | -37.1% | -59.59 to -33.97 | yes, better |
| response time (ms), 95th percentile | 264 | 120 | -54.6% | -172.8 to -115.3 | yes, better |
| response time (ms), 99th percentile | 374.9 | 154.4 | -58.8% | -256.9 to -184.2 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.3667 | 0.2333 | -36.4% | -0.425 to +0.1584 | no |
| utilisation (used / allocatable) | 0.03669 | 0.05626 | +53.3% | +0.01546 to +0.02367 | yes, better |
| CPU used (cores), mean | 0.8806 | 1.112 | +26.3% | +0.1684 to +0.2941 | yes, better |
| energy per core-hour (Wh) | 716.1 | 509.4 | -28.9% | -231.8 to -181.5 | yes, better |
| HPA replicas, mean | 8.816 | 6.565 | -25.5% | -2.952 to -1.549 | yes, better |
| pods started | 4.9 | 2.6 | -46.9% | -3.919 to -0.6811 | yes, better |
| pod start wait, total (s) | 13.8 | 7.1 | -48.6% | -13.26 to -0.1437 | yes, better |
| pod start wait, mean (s) | 2.733 | 1.477 | -45.9% | -2.282 to -0.2302 | yes, better |
