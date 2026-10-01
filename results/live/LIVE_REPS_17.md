# Set 17 on real Kubernetes: native against me on top

Run: benchmark-reps 36356742965, commit 40c95af (two arms; prefer-not idle mark, conveyed CPU, the promise in queue
terms, machines empty one at a time, pod reflex with S and R from the same window). Five paired repetitions, 15
minutes each, kind with 1 control plane and 6 workers.

A change is significant when its paired 95% interval excludes zero. Lower response time is better.

| Gauge | Native | Me on top | Verdict |
|---|---:|---:|---|
| workers in service, mean | 6 | 3.83 | −36.1%, better, significant |
| node-hours | 1.519 | 0.968 | −36.3%, better, significant |
| energy (Wh) | 159.6 | 120.7 | −24.4%, better, significant |
| energy per unit of work (Wh per core-hour) | 679 | 415 | −38.9%, better, significant |
| work done (CPU used, cores) | 0.929 | 1.151 | +23.9%, better, significant |
| response time, mean (ms) | 161.6 | 116.4 | −28.0%, better, significant |
| response time, 95th percentile (ms) | 323.6 | 212.2 | −34.4%, better, significant |
| response time, 99th percentile (ms) | 457.9 | 306.5 | −33.1%, better, significant |
| failed requests (%) | 0 | 0 | equal |
| pods not yet running, pod-minutes | 0.21 | 0.977 | +365%, worse, significant |
| replicas, mean | 8.91 | 9.18 | +3.0%, not significant |

## What the trail shows (repetition 1)

**Pods not yet running.** Every one of them is a pod start native never makes.
- **My pod reflex** raised the replica floor to 10 and released it 11 times, plus three smaller floors, in one run:
  "floor 10 (queue busy 0.47 vs promise 0.20, R 156 ms, S 83 ms)" then "release floor 10 -> 1".
- **The HPA target** I held moved 278% → 185% → 138% → 82% → 50% as the pods' conveyed limits changed with how many
  shared a machine.
- Each raise, and each lower target, made the autoscaler start pods. Each start is seconds of a pod not yet running.

**What I do about it (set 18).**
- The autoscaler alone makes and removes pods. My pod reflex gauges the queue and writes nothing.
- The target I hold uses the CPU each pod is guaranteed across the machines in service, so it moves only when a
  machine idles or wakes.
