# Live repetitions, set 3: GitHub Actions run 36289557446 (commit 9892270), 5 × native / omni / strict on kind

This is the first set with the probe through the Service (NodePort via kube-proxy) and the PodDisruptionBudget, and
the first live set with the supervisory nervous system gating machine release.

## B: Omni-Compass on top vs native, 5 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 6 | +0.0% | -3.155e-16 to +6.708e-16 | no |
| node-hours | 1.517 | 1.516 | -0.1% | -0.02125 to +0.01859 | no |
| energy (Wh) | 168.1 | 165.7 | -1.4% | -7.697 to +2.854 | no |
| response time (ms), mean | 221.7 | 210.3 | -5.1% | -57.38 to +34.55 | no |
| response time (ms), 95th percentile | 431.4 | 440.2 | +2.0% | -47.09 to +64.69 | no |
| response time (ms), 99th percentile | 568.9 | 609 | +7.0% | -51.68 to +131.8 | no |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.3433 | 0.3967 | +15.5% | -0.4106 to +0.5172 | no |
| utilisation (used / allocatable) | 0.07676 | 0.06667 | -13.1% | -0.02607 to +0.005892 | no |

## C: Omni-Compass decides (strict) vs native, 5 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 6 | +0.0% | -7.797e-16 to +7.797e-16 | no |
| node-hours | 1.517 | 1.518 | +0.0% | -0.00974 to +0.01041 | no |
| energy (Wh) | 168.1 | 166.4 | -1.0% | -4.867 to +1.447 | no |
| response time (ms), mean | 221.7 | 217.8 | -1.8% | -89.74 to +81.98 | no |
| response time (ms), 95th percentile | 431.4 | 463.2 | +7.4% | -105.7 to +169.4 | no |
| response time (ms), 99th percentile | 568.9 | 629 | +10.6% | -155.4 to +275.7 | no |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.3433 | 0.8033 | +134.0% | +0.05385 to +0.8661 | yes, worse |
| utilisation (used / allocatable) | 0.07676 | 0.06928 | -9.8% | -0.01814 to +0.003173 | no |

## Reading

**Failed requests.** They are 0% in every arm. The 16-66% of sets 1-2 was the probe's hung tunnel, as diagnosed.

**Machines.** Omni-Compass kept all 6 machines in service in every repetition. Controller log: 15 of 15 decisions,
0 errors, no node-scale command.

- **The likely cause.** With a working probe, p95 sits at 430-460 ms against the 500 ms SLO declared before the run.
  Every window above 500 ms is SLO pressure. That pressure blocks machine release for the next 3 decisions and lowers
  the engine's calm.
- **Why that is odd here.** Machines are at 7% utilisation with no waiting pods. The latency comes from the
  workload's per-request compute, not from a machine shortage.
- **Why the earlier sets differed.** Sets 1-2 released machines because the hung probe produced few or no successful
  samples, so the controller saw little latency pressure. Their machine savings were therefore measured with a blinded
  latency sense and are not claimed.
- **How this will be settled.** The decision trail (p95, SLO state, calm, node authority per decision) is now printed
  in every job log. Set 4 will show which gate held.

**Everything else.** No significant difference from native on any gauge, except that C has more pending pod-minutes
(0.80 vs 0.34 pod-minutes).
