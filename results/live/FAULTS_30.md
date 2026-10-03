# The fault test on kind, re-run (set 30 F): native, Omni-Compass on top with the allocation law, and with the bowl law and the verdict, the operator's HPA target handed back at once when a fault is over, 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps` with `faults: 1`, run 37105046042, commit `acc1c4e`, 2026-10-03, job
`aggregate` (job 111161043506, `python tools/live_reps.py reps`), fixed-rate load, 900 measured seconds per arm.
Transcribed from the job's printed receipt; the run's artifact `live-reps` (zip SHA-256
`f76ab0b2fff54538de8e04a0d21b3fead4ede66e2eea095dc9cc048e6b5669e6`) holds the same tables. Evidence class **L**. The
same four faults at the same moments as the first run (`results/live/FAULTS.md`).

**Against the first run.** Recovery is faster than native from every fault in both arms. With the bowl law, HPA
replicas fell from +8.2% to **+5.6%** (+0.19 to +0.78 pods, significant): still worse, with CPU and machines unchanged and
no energy saved, so still outside the one rule (`DISCLOSURES.md`, section 3). It is not closed by this change; the next
change and its re-run are recorded in `docs/K8S_BOWL_PREREGISTRATION.md`.

## Recovery from each fault

| Fault | Arm | Time to recover (s) | Over the line (%) | Change in recovery against native |
|---|---|---:|---:|---:|
| machine down | native | 65 | 14.0 |  |
| machine down | omni | 40 | 10.1 | -25 s (-38%) |
| machine down | bowl | 43 | 8.9 | -21 s (-33%) |
| spike | native | 249 | 62.4 |  |
| spike | omni | 246 | 40.2 | -3 s (-1%) |
| spike | bowl | 231 | 59.3 | -18 s (-7%) |
| runaway pod started | native | 98 | 10.4 |  |
| runaway pod started | omni | 69 | 4.8 | -29 s (-30%) |
| runaway pod started | bowl | 86 | 7.8 | -12 s (-12%) |
| probe blind | native | 63 | 0.3 |  |
| probe blind | omni | 60 | 0.1 | -3 s (-5%) |
| probe blind | bowl | 54 | 0.0 | -9 s (-14%) |

## B: the engine's allocation law against native, whole run with the faults

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 5.915 | 5.41 | -8.5% | -1.158 to +0.1473 | no |
| node-hours | 1.498 | 1.371 | -8.5% | -0.2974 to +0.04347 | no |
| energy, parked workers still on at idle power (Wh, declared model) | 165.7 | 165.1 | -0.4% | -1.318 to +0.001093 | no |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 164.1 | 153.9 | -6.2% | -22.89 to +2.506 | no |
| response time (ms), mean | 196.8 | 135.9 | -31.0% | -93.16 to -28.67 | yes, better |
| response time (ms), 95th percentile | 377.3 | 188.7 | -50.0% | -256.7 to -120.4 | yes, better |
| response time (ms), 99th percentile | 1082 | 1068 | -1.3% | -851.2 to +823.7 | no |
| time over the response line (% of samples) | 7.581 | 5.26 | -30.6% | -3.469 to -1.171 | yes, better |
| failed requests (%) | 4.624 | 3.739 | -19.1% | -1.481 to -0.289 | yes, better |
| pending pods, pod-minutes | 0.535 | 0.5617 | +5.0% | -0.4836 to +0.5369 | no |
| utilisation (used / allocatable) | 0.06855 | 0.07196 | +5.0% | -0.006874 to +0.01369 | no |
| CPU used (cores), mean | 1.622 | 1.552 | -4.3% | -0.1134 to -0.02584 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.01823 | +0.0182 (native is 0) | +0.01547 to +0.02099 | yes, more |
| CPU used with Omni's own (cores), mean | 1.622 | 1.57 | -3.2% | -0.09315 to -0.009641 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 417.9 | 397.4 | -4.9% | -70.43 to +29.47 | no |
| HPA replicas, mean | 8.606 | 8.782 | +2.0% | -0.1606 to +0.5122 | no |
| pods started | 4.8 | 3.6 | -25.0% | -2.406 to +0.0064 | no |
| pod start wait, total (s) | 18.4 | 6.7 | -63.6% | -18.37 to -5.032 | yes, better |
| pod start wait, mean (s) | 3.417 | 1.582 | -53.7% | -2.636 to -1.034 | yes, better |

## B with the bowl law and the verdict against native, whole run with the faults

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 5.915 | 5.909 | -0.1% | -0.02376 to +0.01042 | no |
| node-hours | 1.498 | 1.492 | -0.4% | -0.01628 to +0.003724 | no |
| energy, parked workers still on at idle power (Wh, declared model) | 165.7 | 165.1 | -0.3% | -1.233 to +0.08506 | no |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 164.1 | 163.4 | -0.4% | -1.556 to +0.1665 | no |
| response time (ms), mean | 196.8 | 112.4 | -42.9% | -133.5 to -35.24 | yes, better |
| response time (ms), 95th percentile | 377.3 | 153.9 | -59.2% | -260.5 to -186.2 | yes, better |
| response time (ms), 99th percentile | 1082 | 898.6 | -17.0% | -1098 to +731.2 | no |
| time over the response line (% of samples) | 7.581 | 5.372 | -29.1% | -2.987 to -1.431 | yes, better |
| failed requests (%) | 4.624 | 4.198 | -9.2% | -0.6318 to -0.2209 | yes, better |
| pending pods, pod-minutes | 0.535 | 0.3533 | -34.0% | -0.4387 to +0.07535 | no |
| utilisation (used / allocatable) | 0.06855 | 0.06799 | -0.8% | -0.001851 to +0.000732 | no |
| CPU used (cores), mean | 1.622 | 1.608 | -0.9% | -0.04283 to +0.01435 | no |
| Omni's own CPU (cores), mean | 0 | 0.00931 | +0.00931 (native is 0) | +0.008296 to +0.01032 | yes, more |
| CPU used with Omni's own (cores), mean | 1.622 | 1.617 | -0.3% | -0.03327 to +0.0234 | no |
| energy per core-hour (Wh, the 25 W standby model) | 417.9 | 419.3 | +0.3% | -5.863 to +8.635 | no |
| HPA replicas, mean | 8.606 | 9.091 | +5.6% | +0.1895 to +0.7808 | yes, worse |
| pods started | 4.8 | 3.7 | -22.9% | -1.887 to -0.3128 | yes, better |
| pod start wait, total (s) | 18.4 | 13.9 | -24.5% | -9.971 to +0.971 | no |
| pod start wait, mean (s) | 3.417 | 2.725 | -20.2% | -1.659 to +0.2759 | no |
