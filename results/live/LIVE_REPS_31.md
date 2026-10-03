# Repeated live runs on kind, set 31: native, Omni-Compass on top with the allocation law, and with the bowl law and the verdict (the operator's HPA target at once when a fault is over; fail up from a blind sense or a lost machine is the operator's own target), 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps`, run 37110007121, commit `0a38e76`, 2026-10-03, job `aggregate`
(job 111175240710, `python tools/live_reps.py reps`), fixed-rate load, 900 measured seconds per arm. Transcribed from the job's
printed receipt; the run's artifact `live-reps` (zip SHA-256 `7423ff466b76abb09aab03ff3f54e0f8c7616bdaf276f0f40af29619a48606f2`) holds the same tables.
Evidence class **L** (real Kubernetes software on kind; energy is a declared model, not a meter).

**No measure in either arm is significantly worse than native.** Total CPU including Omni-Compass's own: bowl −6.1%, allocation law −6.6%.

### B: the engine's allocation law against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.066 | -32.2% | -2.389 to -1.479 | yes, better |
| node-hours | 1.519 | 1.029 | -32.3% | -0.6046 to -0.376 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 159.5 | 158.9 | -0.4% | -1.184 to -0.01903 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 159.5 | 122.2 | -23.4% | -45.68 to -28.95 | yes, better |
| response time (ms), mean | 148.3 | 82.39 | -44.4% | -87.72 to -44.06 | yes, better |
| response time (ms), 95th percentile | 334.7 | 129.3 | -61.4% | -269.1 to -141.7 | yes, better |
| response time (ms), 99th percentile | 557.5 | 195.1 | -65.0% | -489.9 to -234.8 | yes, better |
| time over the response line (% of samples) | 2.144 | 0.0862 | -96.0% | -3.413 to -0.7019 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.29 | 0.08 | -72.4% | -0.4755 to +0.05546 | no |
| utilisation (used / allocatable) | 0.03801 | 0.05113 | +34.5% | +0.008852 to +0.0174 | yes, more |
| CPU used (cores), mean | 0.9122 | 0.8343 | -8.5% | -0.1054 to -0.05034 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.01747 | +0.0175 (native is 0) | +0.01457 to +0.02037 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9122 | 0.8518 | -6.6% | -0.08608 to -0.03472 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 735.8 | 601.8 | -18.2% | -208.8 to -59.17 | yes, better |
| HPA replicas, mean | 8.658 | 5.724 | -33.9% | -3.765 to -2.105 | yes, better |
| pods started | 4.3 | 2.7 | -37.2% | -3.842 to +0.6418 | no |
| pod start wait, total (s) | 13.5 | 5.4 | -60.0% | -16.83 to +0.6311 | no |
| pod start wait, mean (s) | 2.787 | 1.61 | -42.2% | -2.466 to +0.1124 | no |

### B with the bowl law and the verdict against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.379 | -10.4% | -0.6758 to -0.5672 | yes, better |
| node-hours | 1.519 | 1.36 | -10.5% | -0.173 to -0.1461 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 159.5 | 158.8 | -0.4% | -1.117 to -0.3052 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 159.5 | 147 | -7.8% | -13.35 to -11.63 | yes, better |
| response time (ms), mean | 148.3 | 76.48 | -48.4% | -95.33 to -48.28 | yes, better |
| response time (ms), 95th percentile | 334.7 | 113.7 | -66.0% | -289.8 to -152.2 | yes, better |
| response time (ms), 99th percentile | 557.5 | 150.3 | -73.0% | -533 to -281.4 | yes, better |
| time over the response line (% of samples) | 2.144 | 0.01212 | -99.4% | -3.537 to -0.7261 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.29 | 0.025 | -91.4% | -0.5154 to -0.01458 | yes, better |
| utilisation (used / allocatable) | 0.03801 | 0.03932 | +3.4% | +7.597e-05 to +0.002543 | yes, more |
| CPU used (cores), mean | 0.9122 | 0.8473 | -7.1% | -0.09479 to -0.03507 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.00896 | +0.00896 (native is 0) | +0.007639 to +0.01028 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9122 | 0.8562 | -6.1% | -0.08476 to -0.02718 | yes, less |
| energy per core-hour (Wh, the 25 W standby model) | 735.8 | 726.5 | -1.3% | -29.44 to +10.9 | no |
| HPA replicas, mean | 8.658 | 4.803 | -44.5% | -4.254 to -3.457 | yes, better |
| pods started | 4.3 | 0 | -100.0% | -5.518 to -3.082 | yes, better |
| pod start wait, total (s) | 13.5 | 0 | -100.0% | -20.4 to -6.604 | yes, better |
| pod start wait, mean (s) | 2.787 | 0 | -100.0% | -3.751 to -1.822 | yes, better |
