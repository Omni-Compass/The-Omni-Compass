# The cost to match on kind: native, native tuned harder by its operator (HPA target 40, 30, 20), and native with Omni-Compass on top (the allocation law; the bowl law with the verdict), 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps`, run 37094493912, commit `3866266`, 2026-10-03, job `aggregate`
(job 111140097802, `python tools/live_reps.py reps`), fixed-rate load (equal work in every arm), 900 measured seconds
per arm, arms rotated in each repetition. Transcribed from the job's printed receipt; the run's artifact `live-reps`
(zip SHA-256 `9bd1b4a41a23917d1a9e167f1b6ddfaafd76f82dbcd6c6d28a0d9042c0b6408d`) holds the same tables. Evidence class
**L** (real Kubernetes software on kind; energy is a declared model, not a meter). Written before the run:
`docs/K8S_BOWL_PREREGISTRATION.md`, the cost to match.

**The answer.** No native setting tried reached Omni-Compass's response time. Tuned all the way to HPA target 20
(9.86 pods against native's 8.52), native's p95 is 346.6 ms; with Omni-Compass on top it is 123.5 ms (bowl law, 8.29
pods, fewer machines) and 149.4 ms (allocation law, 6.48 pods, 4.13 machines). Tuning the autoscaler buys a native
cluster almost nothing; Omni-Compass on top cuts the p95 by about two thirds with fewer pods and fewer machines.

The receipt printed "nan" for the tuned arms' CPU including Omni-Compass's own: those arms run no Omni process, so
their own CPU is 0 and the column equals their CPU used (0.9728, 0.9596, 0.9567). `tools/live_reps.py` now counts it so.

## The cost to match

| Arm | p95 (ms) | p99 (ms) | HPA replicas | CPU used incl. Omni's own (cores) | Machines in service |
|---|---:|---:|---:|---:|---:|
| Native | 360.9 | 594.4 | 8.521 | 0.971 | 6 |
| Native tuned, HPA target 40 | 350.5 | 584.7 | 9.184 | 0.9728 | 6 |
| Native tuned, HPA target 30 | 348.9 | 546.7 | 9.733 | 0.9596 | 6 |
| Native tuned, HPA target 20 | 346.6 | 570.1 | 9.86 | 0.9567 | 6 |
| Omni on top | 149.4 | 220.6 | 6.484 | 0.9118 | 4.131 |
| Omni on top, bowl law | 123.5 | 163.1 | 8.29 | 0.9332 | 5.797 |

- Omni on top, bowl law (p95 123.5 ms): no native setting tried reached it; the lowest native p95 is 346.6 ms (Native tuned, HPA target 20).
- Omni on top (p95 149.4 ms): no native setting tried reached it; the lowest native p95 is 346.6 ms (Native tuned, HPA target 20).

## B: the engine's allocation law against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.131 | -31.2% | -2.343 to -1.395 | yes, better |
| node-hours | 1.519 | 1.046 | -31.1% | -0.5923 to -0.3539 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160 | 159.5 | -0.3% | -0.9249 to -0.02437 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160 | 124.1 | -22.5% | -44.7 to -27.22 | yes, better |
| response time (ms), mean | 160.6 | 89.69 | -44.1% | -93.13 to -48.59 | yes, better |
| response time (ms), 95th percentile | 360.9 | 149.4 | -58.6% | -275.1 to -147.9 | yes, better |
| response time (ms), 99th percentile | 594.4 | 220.6 | -62.9% | -483.5 to -264.2 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.2617 | 0.185 | -29.3% | -0.4112 to +0.2579 | no |
| utilisation (used / allocatable) | 0.04046 | 0.05391 | +33.3% | +0.008916 to +0.01799 | yes, more |
| CPU used (cores), mean | 0.971 | 0.894 | -7.9% | -0.1053 to -0.04875 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.01787 | +0.0179 (native is 0) | +0.01486 to +0.02088 | yes, more |
| CPU used with Omni's own (cores), mean | 0.971 | 0.9118 | -6.1% | -0.08508 to -0.0332 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 708.9 | 580.3 | -18.2% | -211.9 to -45.44 | yes, better |
| HPA replicas, mean | 8.521 | 6.484 | -23.9% | -3.069 to -1.003 | yes, better |
| pods started | 4.7 | 2.5 | -46.8% | -3.142 to -1.258 | yes, better |
| pod start wait, total (s) | 13.1 | 8.4 | -35.9% | -12.84 to +3.442 | no |
| pod start wait, mean (s) | 2.703 | 3.07 | +13.6% | -2.048 to +2.781 | no |

## B with the bowl law and the verdict against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.797 | -3.4% | -0.2802 to -0.1267 | yes, better |
| node-hours | 1.519 | 1.469 | -3.3% | -0.06941 to -0.03032 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160 | 159.7 | -0.2% | -0.7275 to +0.1494 | no |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160 | 155.9 | -2.6% | -5.595 to -2.713 | yes, better |
| response time (ms), mean | 160.6 | 83.1 | -48.2% | -102.4 to -52.54 | yes, better |
| response time (ms), 95th percentile | 360.9 | 123.5 | -65.8% | -305.9 to -168.8 | yes, better |
| response time (ms), 99th percentile | 594.4 | 163.1 | -72.6% | -560.7 to -301.8 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.2617 | 0.235 | -10.2% | -0.2551 to +0.2018 | no |
| utilisation (used / allocatable) | 0.04046 | 0.03978 | -1.7% | -0.002263 to +0.0009116 | no |
| CPU used (cores), mean | 0.971 | 0.9231 | -4.9% | -0.0838 to -0.01201 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.01012 | +0.0101 (native is 0) | +0.008714 to +0.01153 | yes, more |
| CPU used with Omni's own (cores), mean | 0.971 | 0.9332 | -3.9% | -0.07273 to -0.002839 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 708.9 | 706.7 | -0.3% | -39.39 to +34.91 | no |
| HPA replicas, mean | 8.521 | 8.29 | -2.7% | -0.5002 to +0.03828 | no |
| pods started | 4.7 | 3.3 | -29.8% | -3.024 to +0.2242 | no |
| pod start wait, total (s) | 13.1 | 9.3 | -29.0% | -10.41 to +2.806 | no |
| pod start wait, mean (s) | 2.703 | 2.278 | -15.7% | -1.33 to +0.4801 | no |

Omni's own CPU is the controller's own cost, counted in the next row; it is the only row where native is 0 by
construction. No measure in either Omni-Compass arm is significantly worse than native.
