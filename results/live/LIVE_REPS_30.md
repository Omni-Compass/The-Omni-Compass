# Repeated live runs on kind, set 30: native, Omni-Compass on top with the allocation law, and with the bowl law and the verdict, the operator's HPA target handed back at once when a fault is over, 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps`, run 37105047258, commit `acc1c4e`, 2026-10-03, job `aggregate`
(job 111160884531, `python tools/live_reps.py reps`), fixed-rate load (equal work in every arm), 900 measured seconds
per arm. Transcribed from the job's printed receipt; the run's artifact `live-reps` (zip SHA-256
`d8c72f5fa76a2de0e5d67c0ab200147aeb2734bd8e68bfbbbe6ce6be363e0cb7`) holds the same tables. Evidence class **L**
(real Kubernetes software on kind; energy is a declared model, not a meter).

What changed from set 29: one thing, written before the run (`docs/K8S_BOWL_PREREGISTRATION.md`, the fault test): once
responses are back inside the band, the line is clean and nothing waits, the bowl hands the operator's HPA target back
at once, never held by the autoscaler's window. **No measure in either arm is significantly worse than native.** Total
CPU including Omni-Compass's own: bowl −6.5%, allocation law −6.7%, both inside the 2% rule.

### B: the engine's allocation law against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 3.717 | -38.0% | -2.442 to -2.124 | yes, better |
| node-hours | 1.515 | 0.9409 | -37.9% | -0.6126 to -0.5349 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 159.7 | 159.6 | -0.0% | -0.7725 to +0.6413 | no |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 159.7 | 116.3 | -27.2% | -46.18 to -40.61 | yes, better |
| response time (ms), mean | 166.7 | 103.2 | -38.1% | -78.96 to -48.03 | yes, better |
| response time (ms), 95th percentile | 369.7 | 190.8 | -48.4% | -217.3 to -140.4 | yes, better |
| response time (ms), 99th percentile | 622.2 | 311.9 | -49.9% | -388.1 to -232.4 | yes, better |
| time over the response line (% of samples) | 2.714 | 0.2478 | -90.9% | -3.434 to -1.499 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.2333 | 0.07667 | -67.1% | -0.3132 to -9.185e-05 | yes, better |
| utilisation (used / allocatable) | 0.04087 | 0.05983 | +46.4% | +0.01665 to +0.02127 | yes, more |
| CPU used (cores), mean | 0.9809 | 0.8953 | -8.7% | -0.1005 to -0.07074 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.01992 | +0.0199 (native is 0) | +0.01681 to +0.02303 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9809 | 0.9152 | -6.7% | -0.07889 to -0.05247 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 680.7 | 538.9 | -20.8% | -184.8 to -98.81 | yes, better |
| HPA replicas, mean | 8.835 | 7.559 | -14.4% | -2.03 to -0.5218 | yes, better |
| pods started | 4.1 | 4.4 | +7.3% | -1.486 to +2.086 | no |
| pod start wait, total (s) | 11.8 | 9.3 | -21.2% | -10.34 to +5.338 | no |
| pod start wait, mean (s) | 2.547 | 2.178 | -14.5% | -1.129 to +0.3911 | no |

### B with the bowl law and the verdict against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.405 | -9.9% | -0.6121 to -0.5779 | yes, better |
| node-hours | 1.515 | 1.37 | -9.5% | -0.1546 to -0.1347 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 159.7 | 159.7 | +0.0% | -0.868 to +1.028 | no |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 159.7 | 148.4 | -7.0% | -12.21 to -10.25 | yes, better |
| response time (ms), mean | 166.7 | 83.82 | -49.7% | -105.2 to -60.53 | yes, better |
| response time (ms), 95th percentile | 369.7 | 129.7 | -64.9% | -295.8 to -184.2 | yes, better |
| response time (ms), 99th percentile | 622.2 | 186.5 | -70.0% | -544.6 to -326.8 | yes, better |
| time over the response line (% of samples) | 2.714 | 0.03636 | -98.7% | -3.706 to -1.649 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.2333 | 0.1833 | -21.4% | -0.3134 to +0.2134 | no |
| utilisation (used / allocatable) | 0.04087 | 0.0419 | +2.5% | +0.0005909 to +0.001464 | yes, more |
| CPU used (cores), mean | 0.9809 | 0.9064 | -7.6% | -0.09339 to -0.05561 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.01074 | +0.0107 (native is 0) | +0.009274 to +0.01221 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9809 | 0.9172 | -6.5% | -0.08147 to -0.04606 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 680.7 | 678.2 | -0.4% | -13.39 to +8.281 | no |
| HPA replicas, mean | 8.835 | 5.988 | -32.2% | -3.227 to -2.467 | yes, better |
| pods started | 4.1 | 1.6 | -61.0% | -3.9 to -1.1 | yes, better |
| pod start wait, total (s) | 11.8 | 3.8 | -67.8% | -13.27 to -2.733 | yes, better |
| pod start wait, mean (s) | 2.547 | 2.133 | -16.3% | -1.509 to +0.6807 | no |
