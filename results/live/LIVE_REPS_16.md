# Set 16 on real Kubernetes: native against me on top

Run: benchmark-reps 36354068590, commit 2d6fccc (prefer-not idle mark, conveyed CPU, the promise in queue terms,
machines empty one at a time). Five paired repetitions, 15 minutes each, kind with 1 control plane and 6 workers.

A change is significant when its paired 95% interval excludes zero. Lower response time is better.

| Gauge | Native | Me on top | Verdict |
|---|---:|---:|---|
| workers in service, mean | 6 | 3.77 | −37.1%, better, significant |
| node-hours | 1.513 | 0.952 | −37.1%, better, significant |
| energy (Wh) | 158.5 | 118.3 | −25.4%, better, significant |
| energy per unit of work (Wh per core-hour) | 722 | 452 | −37.4%, better, significant |
| work done (CPU used, cores) | 0.875 | 1.051 | +20.0%, better, significant |
| response time, mean (ms) | 116.2 | 82.4 | −29.1%, better, significant |
| response time, 95th percentile (ms) | 244.3 | 144.7 | −40.8%, better, significant |
| response time, 99th percentile (ms) | 367.7 | 234.1 | −36.4%, better, significant |
| failed requests (%) | 0 | 0 | equal |
| pods not yet running, pod-minutes | 0.207 | 0.54 | +161%, not significant (set 15: +488%) |
| replicas, mean | 8.80 | 9.24 | +5.0%, not significant |

## What the trail shows

**Pods not yet running.** With the prefer-not mark no pod waited for a place. What is left is pod starts native never
makes: my pod reflex still raised and released the replica floor. The autoscaler alone makes pods from set 18 on; the
reflex gauges and writes nothing.
