# Repeated live runs on kind, set 24: Omni-Compass on top against native, 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps`, run 36983865216, commit `c908054`, 2026-10-02, job `aggregate`
(`python tools/live_reps.py reps`). Transcribed from the job's printed receipt; the run's artifact `live-reps`
(ID 11218009199, SHA-256 of the zip 28062fb8fd023d4b4cb6847f4d3103a3e7c70f61362118cf11efeaa957870b57) holds the same
table. Evidence class **L** (real Kubernetes software on kind; energy is a declared model, not a meter).

## Mean over repetitions

| Gauge | Native | Omni on top |
|---|---:|---:|
| worker nodes in service, mean | 6 | 4.102 |
| node-hours | 1.519 | 1.038 |
| energy, parked workers still on at idle power (Wh, declared model) | 158.7 | 158.2 |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 158.7 | 122.2 |
| response time (ms), mean | 128.5 | 72.83 |
| response time (ms), 95th percentile | 284.9 | 113.7 |
| response time (ms), 99th percentile | 446.2 | 160.2 |
| failed requests (%) | 0 | 0 |
| pending pods, pod-minutes | 0.3133 | 0.02667 |
| utilisation (used / allocatable) | 0.0347 | 0.04575 |
| CPU used (cores), mean | 0.8328 | 0.7562 |
| Omni's own CPU (cores), mean | 0 | 0.06125 |
| CPU used with Omni's own (cores), mean | 0.8328 | 0.8175 |
| energy per core-hour (Wh, the 25 W standby model) | 811.7 | 672 |
| HPA replicas, mean | 8.365 | 5.134 |
| pods started | 4.3 | 2 |
| pod start wait, total (s) | 14.5 | 3.8 |
| pod start wait, mean (s) | 2.777 | 1.25 |

**Energy on kind is a declared model, not a meter.** Every worker stays powered and Ready in every arm; the first
energy row counts a parked worker at its full idle power, which is what kind does. The second counts it at the
declared standby power, which needs a node autoscaler that really removes the machine; this run has none.

## Omni-Compass on top against native, 10 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.102 | -31.6% | -2.43 to -1.365 | yes, better |
| node-hours | 1.519 | 1.038 | -31.7% | -0.616 to -0.3472 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 158.7 | 158.2 | -0.3% | -0.8624 to -0.1587 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 158.7 | 122.2 | -23.0% | -46.44 to -26.62 | yes, better |
| response time (ms), mean | 128.5 | 72.83 | -43.3% | -78.51 to -32.72 | yes, better |
| response time (ms), 95th percentile | 284.9 | 113.7 | -60.1% | -233.9 to -108.5 | yes, better |
| response time (ms), 99th percentile | 446.2 | 160.2 | -64.1% | -372.8 to -199.1 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.3133 | 0.02667 | -91.5% | -0.509 to -0.06435 | yes, better |
| utilisation (used / allocatable) | 0.0347 | 0.04575 | +31.8% | +0.00692 to +0.01518 | yes, more |
| CPU used (cores), mean | 0.8328 | 0.7562 | -9.2% | -0.09991 to -0.05324 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.06125 | +0.0613 (native is 0) | +0.05225 to +0.07025 | yes, more |
| CPU used with Omni's own (cores), mean | 0.8328 | 0.8175 | -1.8% | -0.03412 to +0.003478 | no |
| energy per core-hour (Wh, the 25 W standby model) | 811.7 | 672 | -17.2% | -220.4 to -59.13 | yes, better |
| HPA replicas, mean | 8.365 | 5.134 | -38.6% | -3.899 to -2.563 | yes, better |
| pods started | 4.3 | 2 | -53.5% | -3.847 to -0.7529 | yes, better |
| pod start wait, total (s) | 14.5 | 3.8 | -73.8% | -19.32 to -2.083 | yes, better |
| pod start wait, mean (s) | 2.777 | 1.25 | -55.0% | -2.713 to -0.3417 | yes, better |
