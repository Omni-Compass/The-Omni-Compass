# What I measure on real Kubernetes: native against me on top

The latest paired set is **set 19** (`results/live/LIVE_REPS_19.md`, benchmark-reps run 36362185876, commit d0ddb94).

| Gauge | Native | Me on top | Verdict |
|---|---:|---:|---|
| workers in service, mean | 6 | 5.12 | −14.7%, better, significant |
| energy (Wh) | 158.7 | 143.9 | −9.3%, better, significant |
| energy per unit of work | 754.6 | 578.8 | −23.3%, better, significant |
| work done (CPU used, cores) | 0.835 | 0.992 | +18.8%, better, significant |
| replicas, mean | 8.73 | 5.49 | −37.1%, better, significant |
| response time, mean (ms) | 91.5 | 60.9 | −33.4%, better, significant |
| response time, 95th percentile (ms) | 201.5 | 92.5 | −54.1%, better, significant |
| response time, 99th percentile (ms) | 297.1 | 110.1 | −63.0%, better, significant |
| failed requests (%) | 0 | 0 | equal |
| pods not yet running, pod-minutes | 0.263 | 0.160 | −39.2%, better, not significant |

**How I did it:**
- No pod was moved, evicted or restarted.
- No machine was switched off; an idle machine stays powered and Ready at its floor.
- The autoscaler alone made every pod.

**Earlier sets.** Each earlier set is recorded as measured, with what its trail showed and what changed after it:
`LIVE_REPS_9.md`, `LIVE_REPS_11.md`, `LIVE_REPS_13.md` to `LIVE_REPS_18.md`.
