# Repeated live runs on kind, set 28: native, Omni-Compass on top with the engine's allocation law, and with the bowl law and the verdict, 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps`, run 37087620193, commit `24666d7`, 2026-10-03, job `aggregate`
(job 111111314584, `python tools/live_reps.py reps`), fixed-rate load (equal work in every arm), 900 measured seconds
per arm. Transcribed from the job's printed receipt; the run's artifact `live-reps` (zip SHA-256
`ca308239ad469e9429749ff6b976c46c2320922db99cc4b313f9200ecc4103fd`) holds the same table. Evidence class **L** (real
Kubernetes software on kind; energy is a declared model, not a meter: every worker stays powered in every arm).

The bowl arm gives a machine back only where the verdict (`omnicompass/verdict.py`, stepwise) measures responses at
most 2% slower without it (`docs/K8S_BOWL_PREREGISTRATION.md`, the verdict in the live controller).

### B: the engine's allocation law (`--law governor`) against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.222 | -29.6% | -2.254 to -1.302 | yes, better |
| node-hours | 1.518 | 1.068 | -29.6% | -0.57 to -0.33 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160.2 | 159.8 | -0.3% | -1.033 to +0.1884 | no |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160.2 | 126.1 | -21.3% | -42.97 to -25.38 | yes, better |
| response time (ms), mean | 169.4 | 96.46 | -43.1% | -88.92 to -56.99 | yes, better |
| response time (ms), 95th percentile | 381.9 | 160.4 | -58.0% | -259.9 to -183 | yes, better |
| response time (ms), 99th percentile | 593.3 | 242 | -59.2% | -427.3 to -275.2 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.295 | 0.08 | -72.9% | -0.4664 to +0.03636 | no |
| utilisation (used / allocatable) | 0.04178 | 0.05533 | +32.4% | +0.007892 to +0.01922 | yes, more |
| CPU used (cores), mean | 1.003 | 0.9232 | -7.9% | -0.1021 to -0.05685 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.06784 | +0.0678 (native is 0) | +0.06099 to +0.07469 | yes, more |
| CPU used with Omni's own (cores), mean | 1.003 | 0.9911 | -1.2% | -0.02833 to +0.005093 | no |
| energy per core-hour (Wh, the 25 W standby model) | 653.1 | 550.8 | -15.7% | -162.2 to -42.53 | yes, better |
| HPA replicas, mean | 8.852 | 6.471 | -26.9% | -3.427 to -1.334 | yes, better |
| pods started | 4.9 | 2.8 | -42.9% | -3.834 to -0.3658 | yes, better |
| pod start wait, total (s) | 16.7 | 6.3 | -62.3% | -18.82 to -1.975 | yes, better |
| pod start wait, mean (s) | 3.15 | 1.787 | -43.3% | -2.658 to -0.06823 | yes, better |

### B with the bowl law and the verdict (`--law bowl`) against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.715 | -4.7% | -0.3913 to -0.1779 | yes, better |
| node-hours | 1.518 | 1.442 | -5.0% | -0.1029 to -0.04985 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160.2 | 159.4 | -0.5% | -1.686 to +0.02712 | no |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160.2 | 154 | -3.9% | -8.233 to -4.185 | yes, better |
| response time (ms), mean | 169.4 | 87.65 | -48.3% | -100 to -63.51 | yes, better |
| response time (ms), 95th percentile | 381.9 | 132.4 | -65.3% | -297.3 to -201.6 | yes, better |
| response time (ms), 99th percentile | 593.3 | 186 | -68.6% | -486.5 to -327.9 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.295 | 0 | -100.0% | -0.5233 to -0.06671 | yes, better |
| utilisation (used / allocatable) | 0.04178 | 0.04207 | +0.7% | -0.0009075 to +0.001495 | no |
| CPU used (cores), mean | 1.003 | 0.9626 | -4.0% | -0.06377 to -0.01653 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.0627 | +0.0627 (native is 0) | +0.05672 to +0.06868 | yes, more |
| CPU used with Omni's own (cores), mean | 1.003 | 1.025 | +2.2% | +0.00319 to +0.04191 | yes, more |
| energy per core-hour (Wh, the 25 W standby model) | 653.1 | 650.4 | -0.4% | -22.27 to +16.84 | no |
| HPA replicas, mean | 8.852 | 8.367 | -5.5% | -1.241 to +0.2722 | no |
| pods started | 4.9 | 3.3 | -32.7% | -2.957 to -0.2428 | yes, better |
| pod start wait, total (s) | 16.7 | 8.9 | -46.7% | -13.89 to -1.714 | yes, better |
| pod start wait, mean (s) | 3.15 | 2.241 | -28.9% | -1.846 to +0.02798 | no |
