# Set 13 on real Kubernetes: machines idle by attrition, no pod moved

Run: benchmark-reps 36339800926, commit b0b72fb. Five paired repetitions (native, me on top, me alone back to back on
one runner, order rotated), 15 minutes each, kind with 1 control plane and 6 workers.

A change is significant when its paired 95% interval excludes zero.

| Gauge | Native | Me on top | Me alone |
|---|---:|---:|---:|
| workers in service, mean | 6 | 6 (equal) | 5.82 (−3.0%, not significant) |
| energy (Wh) | 158.6 | 158.4 (−0.2%, not significant) | 155.2 (−2.2%, not significant) |
| response time, mean (ms) | 112.8 | 112.1 (−0.6%, not significant) | 113.1 (+0.2%, not significant) |
| response time, 95th percentile (ms) | 238.4 | 239.9 (+0.7%, not significant) | 239.2 (+0.4%, not significant) |
| response time, 99th percentile (ms) | 373 | 362.6 (−2.8%, not significant) | 352.3 (−5.5%, not significant) |
| failed requests (%) | 0 | 0 | 0 |
| pods not yet running, pod-minutes | 0.277 | 0.213 (−22.9%, not significant) | 0.200 (−27.7%, not significant) |
| utilisation | 0.0353 | 0.0364 (+3.1%, significant) | 0.0376 (+6.6%, not significant) |

## What the trail shows

**Machines.**
- I closed one worker to new work. It still carried one serving pod, so it stayed in service.
- I judged my machine order by the machines in service, so the order read as "did not land", and every further idle
  waited on it. I idled at most one machine, and its pod never left inside the run.
- My orders are now judged by the machines open to work. A closed machine that still carries work stays in the energy
  count at full power until its work leaves on its own.

**Response time.**
- Each serving pod carries a CPU quota of 500m. One request needs a little more than one quota period, so it waits for
  the next period. Two requests on one pod wait several periods: mean 113 ms, 95th percentile 240 ms.
- Meanwhile the machines ran at 3.5% of their CPU.
- The pod reflex never raised a floor, because the queue was not the delay: the quota was.
- I now convey each machine's idle CPU to the pods serving on it, in place, never below the operator's limit
  (`omni_controller/muscles.py`, `convey`).
