# Repeated live runs on kind, set 29: native, Omni-Compass on top with the engine's allocation law, and with the bowl law and the verdict, the controller reading through one kubectl proxy, 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps`, run 37094338955, commit `a3721cc`, 2026-10-03, job `aggregate`
(job 111130515923, `python tools/live_reps.py reps`), fixed-rate load (equal work in every arm), 900 measured seconds
per arm. Transcribed from the job's printed receipt; the run's artifact `live-reps` (zip SHA-256
`9ec964ec39340d8c493f99627d99425bacf8452bd5ac3d7ed7caa69bb8e3b904`) holds the same table. Evidence class **L** (real
Kubernetes software on kind; energy is a declared model, not a meter: every worker stays powered in every arm).

What changed from set 28: one thing, written before the run (`docs/K8S_BOWL_PREREGISTRATION.md`, set 29). The
controller reads through one `kubectl proxy` started once, so a read is a local HTTP request instead of a new kubectl
process. Same arms, load, duration and outcomes.

**Label by the preregistered rule:** total CPU including Omni-Compass's own no more than 2% above native. Bowl law with
the verdict: **−4.7%** (−0.071 to −0.017 cores), **passes, and significantly lower**. Allocation law: −7.7%, passes.
Omni-Compass's own CPU fell from 0.063 cores in set 28 to 0.011 (bowl) and from 0.068 to 0.018 (allocation law). No
measure in either arm is significantly worse than native.

### B: the engine's allocation law (`--law governor`) against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 3.958 | -34.0% | -2.573 to -1.511 | yes, better |
| node-hours | 1.522 | 1.003 | -34.1% | -0.652 to -0.3852 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160 | 159.3 | -0.4% | -1.133 to -0.2884 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160 | 120.5 | -24.7% | -49.3 to -29.71 | yes, better |
| response time (ms), mean | 156.4 | 89.3 | -42.9% | -89.71 to -44.58 | yes, better |
| response time (ms), 95th percentile | 346.9 | 149.2 | -57.0% | -257.8 to -137.7 | yes, better |
| response time (ms), 99th percentile | 571.1 | 245.9 | -56.9% | -444.4 to -206 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.265 | 0.1283 | -51.6% | -0.3747 to +0.1014 | no |
| utilisation (used / allocatable) | 0.03926 | 0.05353 | +36.3% | +0.009594 to +0.01894 | yes, more |
| CPU used (cores), mean | 0.9423 | 0.8514 | -9.7% | -0.1136 to -0.06826 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.0184 | +0.0184 (native is 0) | +0.01528 to +0.02152 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9423 | 0.8698 | -7.7% | -0.09371 to -0.05137 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 722 | 586.9 | -18.7% | -218.3 to -51.81 | yes, better |
| HPA replicas, mean | 8.559 | 6.357 | -25.7% | -3.195 to -1.209 | yes, better |
| pods started | 3.9 | 3.2 | -17.9% | -2.008 to +0.6081 | no |
| pod start wait, total (s) | 11.2 | 6.2 | -44.6% | -10.93 to +0.9274 | no |
| pod start wait, mean (s) | 2.64 | 2.126 | -19.5% | -2.625 to +1.597 | no |

### B with the bowl law and the verdict (`--law bowl`) against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.697 | -5.1% | -0.4104 to -0.1961 | yes, better |
| node-hours | 1.522 | 1.443 | -5.2% | -0.1059 to -0.05226 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160 | 159.3 | -0.4% | -1.41 to -0.00945 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160 | 153.6 | -4.0% | -8.397 to -4.535 | yes, better |
| response time (ms), mean | 156.4 | 80.28 | -48.7% | -100.7 to -51.63 | yes, better |
| response time (ms), 95th percentile | 346.9 | 123.5 | -64.4% | -289.7 to -157.1 | yes, better |
| response time (ms), 99th percentile | 571.1 | 165.2 | -71.1% | -535.4 to -276.5 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.265 | 0.1567 | -40.9% | -0.4418 to +0.2252 | no |
| utilisation (used / allocatable) | 0.03926 | 0.03882 | -1.1% | -0.001565 to +0.0006847 | no |
| CPU used (cores), mean | 0.9423 | 0.8874 | -5.8% | -0.08301 to -0.02676 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.01081 | +0.0108 (native is 0) | +0.009254 to +0.01237 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9423 | 0.8982 | -4.7% | -0.07111 to -0.01704 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 722 | 724 | +0.3% | -23.85 to +27.98 | no |
| HPA replicas, mean | 8.559 | 7.907 | -7.6% | -1.284 to -0.01979 | yes, better |
| pods started | 3.9 | 3.1 | -20.5% | -2.097 to +0.4972 | no |
| pod start wait, total (s) | 11.2 | 8 | -28.6% | -7.918 to +1.518 | no |
| pod start wait, mean (s) | 2.64 | 2.61 | -1.1% | -0.872 to +0.812 | no |
