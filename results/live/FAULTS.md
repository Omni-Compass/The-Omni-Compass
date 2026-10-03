# The fault test on kind: native, Omni-Compass on top with the allocation law, and with the bowl law and the verdict, the same four faults at the same moments, 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps` with `faults: true`, run 37094604580, commit `a149d4e`, 2026-10-03,
job `aggregate` (job 111131311878, `python tools/live_reps.py reps`), fixed-rate load, 900 measured seconds per arm.
Transcribed from the job's printed receipt; the run's artifact `live-reps` (zip SHA-256
`d89ccf1f836b9805d21668b6d8c1eb449bac393b04d12062775493b580f0a39c`) holds the same tables. Evidence class **L**.
Faults (`scripts/kind_faults.sh`, written before the run in `docs/K8S_BOWL_PREREGISTRATION.md`): a worker machine
stopped at 15% of the run for two minutes; traffic tripled at 35% for two minutes; a pod with no CPU limit burning CPU
at 55% for two minutes; the response-time probe blind at 75% for one minute.

## Recovery from each fault

Time to recover: from the fault's start until responses stay under the line for 30 seconds straight (at most 300 s).
Over the line: the share of response samples over the line or failed in the 300 seconds after the fault. Paired means
over the repetitions; lower is better in both.

| Fault | Arm | Time to recover (s) | Over the line (%) | Change in recovery against native |
|---|---|---:|---:|---:|
| machine down | native | 56 | 13.6 |  |
| machine down | omni | 40 | 9.3 | -16 s (-29%) |
| machine down | bowl | 48 | 9.7 | -8 s (-14%) |
| spike | native | 252 | 63.1 |  |
| spike | omni | 235 | 41.1 | -18 s (-7%) |
| spike | bowl | 237 | 57.3 | -15 s (-6%) |
| runaway pod started | native | 110 | 10.1 |  |
| runaway pod started | omni | 72 | 5.3 | -38 s (-35%) |
| runaway pod started | bowl | 91 | 8.0 | -19 s (-17%) |
| probe blind | native | 61 | 0.3 |  |
| probe blind | omni | 60 | 0.1 | -1 s (-2%) |
| probe blind | bowl | 60 | 0.1 | -1 s (-1%) |

## B: the engine's allocation law against native, whole run with the faults

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 5.914 | 5.268 | -10.9% | -1.346 to +0.05437 | no |
| node-hours | 1.501 | 1.333 | -11.2% | -0.3468 to +0.01107 | no |
| energy, parked workers still on at idle power (Wh, declared model) | 166.3 | 165.2 | -0.7% | -1.846 to -0.3929 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 164.7 | 151.3 | -8.1% | -26.35 to -0.3213 | yes, better |
| response time (ms), mean | 225.1 | 131.2 | -41.7% | -145.6 to -42.27 | yes, better |
| response time (ms), 95th percentile | 385.3 | 180.6 | -53.1% | -262 to -147.2 | yes, better |
| response time (ms), 99th percentile | 1348 | 990.5 | -26.5% | -876.5 to +161.2 | no |
| time over the response line (% of samples) | 7.473 | 5.164 | -30.9% | -3.398 to -1.22 | yes, better |
| failed requests (%) | 4.614 | 3.694 | -19.9% | -1.726 to -0.1131 | yes, better |
| pending pods, pod-minutes | 0.8533 | 0.3283 | -61.5% | -0.9293 to -0.1207 | yes, better |
| utilisation (used / allocatable) | 0.06942 | 0.07459 | +7.5% | -0.005818 to +0.01616 | no |
| CPU used (cores), mean | 1.642 | 1.565 | -4.7% | -0.1366 to -0.01825 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.01827 | +0.0183 (native is 0) | +0.01569 to +0.02085 | yes, more |
| CPU used with Omni's own (cores), mean | 1.642 | 1.583 | -3.6% | -0.1166 to -0.001706 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 413.4 | 386.7 | -6.5% | -82.6 to +29.14 | no |
| HPA replicas, mean | 8.595 | 8.781 | +2.2% | -0.1422 to +0.5148 | no |
| pods started | 5 | 3.9 | -22.0% | -2.425 to +0.2254 | no |
| pod start wait, total (s) | 33.3 | 7.8 | -76.6% | -49.65 to -1.353 | yes, better |
| pod start wait, mean (s) | 6.274 | 1.699 | -72.9% | -9.359 to +0.2089 | no |

## B with the bowl law and the verdict against native, whole run with the faults

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 5.914 | 5.914 | +0.0% | -0.0006419 to +0.0008108 | no |
| node-hours | 1.501 | 1.499 | -0.2% | -0.006682 to +0.002126 | no |
| energy, parked workers still on at idle power (Wh, declared model) | 166.3 | 166 | -0.2% | -0.916 to +0.2708 | no |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 164.7 | 164.3 | -0.2% | -0.9127 to +0.2758 | no |
| response time (ms), mean | 225.1 | 119.5 | -46.9% | -166.1 to -45.09 | yes, better |
| response time (ms), 95th percentile | 385.3 | 174.5 | -54.7% | -294.5 to -127 | yes, better |
| response time (ms), 99th percentile | 1348 | 585.1 | -56.6% | -1252 to -274.1 | yes, better |
| time over the response line (% of samples) | 7.473 | 5.785 | -22.6% | -2.896 to -0.4785 | yes, better |
| failed requests (%) | 4.614 | 4.572 | -0.9% | -0.5208 to +0.4377 | no |
| pending pods, pod-minutes | 0.8533 | 0.37 | -56.6% | -1 to +0.03331 | no |
| utilisation (used / allocatable) | 0.06942 | 0.06908 | -0.5% | -0.002104 to +0.001427 | no |
| CPU used (cores), mean | 1.642 | 1.634 | -0.5% | -0.0497 to +0.03376 | no |
| Omni's own CPU (cores), mean | 0 | 0.00883 | +0.00883 (native is 0) | +0.007619 to +0.01004 | yes, more |
| CPU used with Omni's own (cores), mean | 1.642 | 1.643 | +0.1% | -0.04045 to +0.04216 | no |
| energy per core-hour (Wh, the 25 W standby model) | 413.4 | 412.8 | -0.2% | -11.59 to +10.27 | no |
| HPA replicas, mean | 8.595 | 9.296 | +8.2% | +0.409 to +0.9946 | yes, worse |
| pods started | 5 | 3.8 | -24.0% | -2.845 to +0.445 | no |
| pod start wait, total (s) | 33.3 | 12.9 | -61.3% | -42.38 to +1.583 | no |
| pod start wait, mean (s) | 6.274 | 2.371 | -62.2% | -8.239 to +0.4342 | no |
