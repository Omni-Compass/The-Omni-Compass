# Repeated live runs on kind, set 25: native against Omni-Compass on top (the engine's allocation law), 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps`, run 37057508359, commit `6fa7a97`, 2026-10-02, job `aggregate`
(`python tools/live_reps.py reps`), fixed-rate load (equal work in every arm), 900 measured seconds per arm. Transcribed
from the job's printed receipt; the run's artifact `live-reps` holds the same table. Evidence class **L** (real
Kubernetes software on kind; energy is a declared model, not a meter: every worker stays powered in every arm).

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.06 | -32.3% | -2.414 to -1.466 | yes, better |
| node-hours | 1.522 | 1.028 | -32.5% | -0.6152 to -0.3728 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160.3 | 159.7 | -0.4% | -1.301 to -0.02267 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160.3 | 122.8 | -23.4% | -46.54 to -28.43 | yes, better |
| response time (ms), mean | 161.2 | 93.2 | -42.2% | -88.89 to -47.18 | yes, better |
| response time (ms), 95th percentile | 360.9 | 154.1 | -57.3% | -268 to -145.5 | yes, better |
| response time (ms), 99th percentile | 591.7 | 233.9 | -60.5% | -465.4 to -250.1 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.34 | 0.07833 | -77.0% | -0.4377 to -0.08564 | yes, better |
| utilisation (used / allocatable) | 0.04038 | 0.05504 | +36.3% | +0.01047 to +0.01884 | yes, more |
| CPU used (cores), mean | 0.9692 | 0.8967 | -7.5% | -0.0893 to -0.05579 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.06707 | +0.0671 (native is 0) | +0.05819 to +0.07595 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9692 | 0.9638 | -0.6% | -0.01834 to +0.007399 | no |
| energy per core-hour (Wh, the 25 W standby model) | 698.7 | 570.9 | -18.3% | -192.8 to -62.8 | yes, better |
| HPA replicas, mean | 8.877 | 6.72 | -24.3% | -3.143 to -1.17 | yes, better |
| pods started | 3.5 | 3 | -14.3% | -2.355 to +1.355 | no |
| pod start wait, total (s) | 13 | 6.2 | -52.3% | -15.37 to +1.769 | no |
| pod start wait, mean (s) | 2.81 | 1.86 | -33.8% | -2.145 to +0.2448 | no |
