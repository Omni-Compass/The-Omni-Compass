# What I measured on real Kubernetes: native, me on top, me alone

**The cluster.** Real Kubernetes (kind: 1 control plane, 6 workers) on GitHub runners.

**The runs.**
- Five repetitions. In each, the three arms run back to back on the same machine, each on a fresh cluster, in an order
  that rotates by repetition.
- Every run lasts 15 minutes under the same stepped load, measured by the same response-time probe through the Service.

**How to read the table.** A change is significant when its paired 95% interval excludes zero.

**Energy.** A worker I park stays powered and Ready at its idle floor (0.25 × idle power). I never switch a machine off.

Run: benchmark-reps 36334030616, commit 5a411aa.

## The three columns (mean of 5 paired repetitions)

| Gauge | Native | Me on top | Me alone |
|---|---:|---:|---:|
| workers in service, mean | 6 | 2.61 | 2.24 |
| node-hours | 1.51 | 0.658 | 0.563 |
| energy (Wh) | 158.3 | 94.6 | 87.5 |
| response time, mean (ms) | 134.1 | 130.4 | 129.1 |
| response time, 95th percentile (ms) | 287.2 | 272.7 | 260.1 |
| response time, 99th percentile (ms) | 413.4 | 399.6 | 380.0 |
| failed requests (%) | 0 | 0 | 0 |
| pods not yet running, pod-minutes | 0.263 | 0.743 | 0.997 |
| utilisation (used / allocatable) | 0.037 | 0.084 | 0.094 |

## Paired against native

**Me on top:**

| Gauge | Change | Significant? |
|---|---:|---|
| workers in service | −56.5% | better |
| energy | −40.2% | better |
| p95 | −5.1% | not significant |
| p99 | −3.3% | not significant |
| mean response | −2.7% | not significant |
| failed requests | 0 | equal |
| pods not yet running | +182% | worse |

**Me alone:**

| Gauge | Change | Significant? |
|---|---:|---|
| workers in service | −62.7% | better |
| energy | −44.7% | better |
| p95 | −9.4% | better |
| p99 | −8.1% | better |
| mean response | −3.7% | better |
| failed requests | 0 | equal |
| pods not yet running | +279% | not significant |

## What the trail shows

**Machines.** I gave back one machine per decision, each time with every sense live and my last order landed:
6 → 5 → 4 → 3 → 2 → 1. At one machine my gate held: no release leaves fewer than one.

**Make before break.** Before emptying a serving machine, its replacements answered elsewhere ("ready 10 of 10 before
draining"). No request failed in any run.

**My own cost.** 22.4 CPU-seconds over 896 s (0.025 of one core).

**The one gauge that rose: pods not yet running.** A pod is "not yet running" from its creation until it starts,
seconds each. To empty a serving machine I first start replacements, then evict. Each machine I emptied therefore
started new pods, and the floor rose to the autoscaler's maximum while the move was under way. Those starts are what
this gauge counts. Service was untouched: p95, p99 and failed requests are all equal or better.

## What I do about it

**Empty machines by attrition, not eviction.** I mark the pods on a machine I intend to park as the first to go
(`controller.kubernetes.io/pod-deletion-cost`) and cordon the machine. When the load falls, the autoscaler's own
scale-down removes those pods first, and the machine is parked when it is empty. No pod is evicted and no replacement is
started. Surge replacement stays only for a machine that must be emptied while the load is rising.

**Energy accounting.** A cordoned machine still serving pods counts as in service, at full power, until it is empty.
