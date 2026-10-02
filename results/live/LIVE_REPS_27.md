# Repeated live runs on kind, set 27: native, Omni-Compass on top with the engine's allocation law, and with the bowl law as aligned with the GPU governor, 10 paired repetitions

Source: GitHub Actions workflow `benchmark-reps`, run 37071353971, commit `d46c959`, 2026-10-02, job `aggregate`
(job 111067346619, `python tools/live_reps.py reps`), fixed-rate load (equal work in every arm), 900 measured seconds
per arm. Transcribed from the job's printed receipt; the run's artifact `live-reps` (artifact 11257320626, zip SHA-256
`7bc1ad7cb199312a6fb28f00352ac57ee4f70211801d43775b3a5c3e92e15dac`) holds the same table. Evidence class **L** (real
Kubernetes software on kind; energy is a declared model, not a meter: every worker stays powered in every arm).

The bowl arm here reads the service as the GPU governor does: the mean response time of the latency window between a
tenth of the SLO and the SLO, held at center 0.4; p95 at or past the SLO, a blind probe or a pending pod is past the
wall (`docs/K8S_BOWL_PREREGISTRATION.md`, set 27).

## All columns, mean over repetitions

| Gauge | Native | Omni on top | Omni on top, bowl law |
|---|---:|---:|---:|
| worker nodes in service, mean | 6 | 3.802 | 5.044 |
| node-hours | 1.523 | 0.9622 | 1.274 |
| energy, parked workers still on at idle power (Wh, declared model) | 160.1 | 159.3 | 158.8 |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160.1 | 117.6 | 140.7 |
| response time (ms), mean | 157.5 | 96.21 | 80.88 |
| response time (ms), 95th percentile | 357.2 | 167.6 | 123.3 |
| response time (ms), 99th percentile | 598.4 | 277.2 | 164.2 |
| failed requests (%) | 0 | 0 | 0 |
| pending pods, pod-minutes | 0.34 | 0.05167 | 0.345 |
| utilisation (used / allocatable) | 0.03908 | 0.05635 | 0.04253 |
| CPU used (cores), mean | 0.9378 | 0.8698 | 0.8716 |
| Omni's own CPU (cores), mean | 0 | 0.06774 | 0.06778 |
| CPU used with Omni's own (cores), mean | 0.9378 | 0.9375 | 0.9393 |
| energy per core-hour (Wh, the 25 W standby model) | 733.2 | 576 | 678.2 |
| HPA replicas, mean | 8.482 | 6.895 | 7.996 |
| pods started | 3.9 | 3.7 | 2.8 |
| pod start wait, total (s) | 13.8 | 8.6 | 6.5 |
| pod start wait, mean (s) | 3.135 | 2.07 | 1.45 |

**Energy on kind is a declared model, not a meter.** Every worker stays powered and Ready in every arm; the first
energy row counts a parked worker at its full idle power, which is what kind does. The second counts it at the
declared standby power, which needs a node autoscaler that really removes the machine; this run has none.

### B: the engine's allocation law (`--law governor`) against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 3.802 | -36.6% | -2.495 to -1.902 | yes, better |
| node-hours | 1.523 | 0.9622 | -36.8% | -0.6348 to -0.4868 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160.1 | 159.3 | -0.5% | -1.562 to -0.04345 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160.1 | 117.6 | -26.6% | -47.97 to -37.08 | yes, better |
| response time (ms), mean | 157.5 | 96.21 | -38.9% | -82.18 to -40.36 | yes, better |
| response time (ms), 95th percentile | 357.2 | 167.6 | -53.1% | -245.4 to -133.7 | yes, better |
| response time (ms), 99th percentile | 598.4 | 277.2 | -53.7% | -419.8 to -222.5 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.34 | 0.05167 | -84.8% | -0.4746 to -0.102 | yes, better |
| utilisation (used / allocatable) | 0.03908 | 0.05635 | +44.2% | +0.0148 to +0.01974 | yes, more |
| CPU used (cores), mean | 0.9378 | 0.8698 | -7.3% | -0.08501 to -0.05107 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.06774 | +0.0677 (native is 0) | +0.05769 to +0.07779 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9378 | 0.9375 | -0.0% | -0.01744 to +0.01684 | no |
| energy per core-hour (Wh, the 25 W standby model) | 733.2 | 576 | -21.4% | -217.6 to -96.64 | yes, better |
| HPA replicas, mean | 8.482 | 6.895 | -18.7% | -2.43 to -0.7439 | yes, better |
| pods started | 3.9 | 3.7 | -5.1% | -1.774 to +1.374 | no |
| pod start wait, total (s) | 13.8 | 8.6 | -37.7% | -14.31 to +3.909 | no |
| pod start wait, mean (s) | 3.135 | 2.07 | -34.0% | -2.465 to +0.3349 | no |

### B with the bowl law (`--law bowl`, as wired at `d46c959`: mean response in the window, center 0.4) against native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.044 | -15.9% | -1.462 to -0.4497 | yes, better |
| node-hours | 1.523 | 1.274 | -16.3% | -0.374 to -0.1236 | yes, better |
| energy, parked workers still on at idle power (Wh, declared model) | 160.1 | 158.8 | -0.8% | -2.309 to -0.2489 | yes, better |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 160.1 | 140.7 | -12.1% | -28.5 to -10.3 | yes, better |
| response time (ms), mean | 157.5 | 80.88 | -48.6% | -105 to -48.16 | yes, better |
| response time (ms), 95th percentile | 357.2 | 123.3 | -65.5% | -311.8 to -156.1 | yes, better |
| response time (ms), 99th percentile | 598.4 | 164.2 | -72.6% | -584.8 to -283.5 | yes, better |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.34 | 0.345 | +1.5% | -0.3727 to +0.3827 | no |
| utilisation (used / allocatable) | 0.03908 | 0.04253 | +8.8% | +0.0002361 to +0.006676 | yes, more |
| CPU used (cores), mean | 0.9378 | 0.8716 | -7.1% | -0.08612 to -0.04644 | yes, less |
| Omni's own CPU (cores), mean | 0 | 0.06778 | +0.0678 (native is 0) | +0.05768 to +0.07788 | yes, more |
| CPU used with Omni's own (cores), mean | 0.9378 | 0.9393 | +0.2% | -0.01386 to +0.01686 | no |
| energy per core-hour (Wh, the 25 W standby model) | 733.2 | 678.2 | -7.5% | -126.4 to +16.61 | no |
| HPA replicas, mean | 8.482 | 7.996 | -5.7% | -1.117 to +0.1462 | no |
| pods started | 3.9 | 2.8 | -28.2% | -3.079 to +0.8792 | no |
| pod start wait, total (s) | 13.8 | 6.5 | -52.9% | -14.66 to +0.06492 | no |
| pod start wait, mean (s) | 3.135 | 1.45 | -53.7% | -2.74 to -0.6304 | yes, better |

**Label of the bowl arm by the preregistered rule** (`docs/K8S_BOWL_PREREGISTRATION.md`): p95 not worse (the whole
interval below 0), failed requests not higher, machines in service down with the whole interval below 0:
**better on machines within the band**.
