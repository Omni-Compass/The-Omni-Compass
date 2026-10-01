# Set 14 on real Kubernetes: idle CPU conveyed to the work

Run: benchmark-reps 36346848307, commit 7d07754. Five paired repetitions (native, me on top, me alone back to back on
one runner, order rotated), 15 minutes each, kind with 1 control plane and 6 workers.

A change is significant when its paired 95% interval excludes zero. Lower response time is better.

| Gauge | Native | Me on top | Me alone |
|---|---:|---:|---:|
| response time, mean (ms) | 162.1 | 98.7 (−39.1%, better, significant) | 97.4 (−39.9%, better, significant) |
| response time, 95th percentile (ms) | 328.5 | 152.3 (−53.6%, better, significant) | 150.7 (−54.1%, better, significant) |
| response time, 99th percentile (ms) | 473.9 | 204.3 (−56.9%, better, significant) | 179.5 (−62.1%, better, significant) |
| failed requests (%) | 0 | 0 (equal) | 0 (equal) |
| utilisation, work done (used / allocatable) | 0.0386 | 0.0529 (+36.8%, better, significant) | 0.0519 (+34.3%, better, significant) |
| workers in service, mean | 6 | 6 (equal) | 6 (equal; the interval is a rounding artefact) |
| node-hours | 1.516 | 1.515 (−0.1%, not significant) | 1.524 (+0.5%, worse, significant) |
| energy (Wh) | 159.3 | 162.4 (+1.9%, worse, significant) | 163.2 (+2.4%, worse, significant) |
| pods not yet running, pod-minutes | 0.053 | 0.32 (+500%, not significant) | 0.107 (+100%, not significant) |

**Useful work per unit of energy** (work done ÷ energy, from the means above, not itself paired-tested): +34% on top, +31% alone. The clients wait for
each answer before asking again, so faster answers bring more requests: 37% more work for 2% more energy.

## What the trail shows

**Response time.** Each machine's idle CPU reached the pods serving on it: 1850m per pod where two pods share a
machine, against the operator's 500m, in place, with no pod restarted.

**Machines.**
- I closed five of six machines to new work (6 → 1 open), but none emptied.
- Each pod now ran busier against its 200m request, because its limit was 1850m. The autoscaler, which sizes against
  the request, held replicas at its maximum of 10, and my own decision in the alone column did the same, so no pod left.
- With every closed machine's pods marked equally, each scale-down would have taken one pod from each machine and
  emptied none.

**What I do about it.**
- **Replicas.** The operator's promise, in queue terms, is busy = target × request ÷ limit. While I convey g times the
  operator's limit, the target that keeps each pod exactly as busy is g times higher, and my replica decision in the
  alone column reads the same promise.
- **Machines.** The closed machine with the least work is marked first to go, the next after it, so each scale-down
  empties whole machines, one at a time.
