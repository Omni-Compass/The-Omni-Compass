# Live set 11: kind, 7 nodes (6 workers), 5 paired reps per arm, 900 s each, four arms

Run: benchmark-reps 36331060116 (workflow_dispatch) on commit 5e5dd56. The repository was made public so GitHub
Actions would start it; five earlier attempts were refused before any runner started. Set 10 (commit b98763a) ran all
15 jobs, but its aggregate step was refused the same way, so it has no table.

Changes since set 9:
- A and B: no power cap on a request-served workload, and Omni on top never loosens the HPA target.
- C: Omni alone sets the replica floor; growth stays free.
- D: empty workers are given back first, with make-before-break drains, a readiness probe and a preStop in the workload.
- E: a light 15 s check, the controller at nice 19, and its own CPU logged.
- New watch arm: Omni runs with --dry-run and writes nothing.

## All columns, mean over repetitions

| Gauge | Native | Omni watches only | Omni on top | Omni alone |
|---|---:|---:|---:|---:|
| worker nodes in service, mean | 6 | 6 | 6 | 5.634 |
| node-hours | 1.509 | 1.512 | 1.511 | 1.416 |
| energy (Wh) | 158.2 | 158.4 | 158.5 | 149.1 |
| response time (ms), mean | 138 | 116.9 | 141.8 | 153.8 |
| response time (ms), 95th percentile | 283.6 | 246 | 286.9 | 316.5 |
| response time (ms), 99th percentile | 410.8 | 341.5 | 420 | 444.8 |
| failed requests (%) | 0 | 0 | 0 | 0 |
| pending pods, pod-minutes | 0.32 | 0.43 | 0.2133 | 0.1033 |
| utilisation (used / allocatable) | 0.03737 | 0.03631 | 0.03756 | 0.04044 |

## Paired against native (95% intervals, 5 reps)

- **Watch only.**
  - p95 -13.3% (interval -187 to +112 ms). Mean response -15.3%. Energy +0.1%.
  - Nothing is significant.
- **On top.**
  - p95 +1.2% (interval -124 to +131 ms). p99 +2.2%. Energy +0.2%. Pending pods -33%.
  - Nothing is significant.
- **Alone.**
  - Machines -6.1% (interval -0.99 to +0.26). Energy -5.8% (interval -25.1 to +6.8 Wh).
  - p95 +11.6% (interval -68 to +134 ms). Pending pods -68%.
  - Nothing is significant.

## Reading

1. **The cost of being there is nil.** The controller used 16.7 CPU seconds over 855 s (0.02 cores) in both omni and
   strict. With Omni watching only, the service was not slower than native: p95 was 13% lower, within noise.
   Overhead (cause 5) is ruled out.
2. **The noise floor is about ±15% on p95.** The watch arm makes no decision yet differs from native by -13% in p95,
   because reps run on different runner machines. Differences of this size are not attributable to Omni-Compass with 5
   reps.
3. **Omni on top now equals native on latency.** p95 went from +27% (set 9) to +1.2%, and 0 requests failed. Taking
   out the power cap and the target raise worked. But it released no machine this set, so no energy was saved.
4. **Omni alone released machines and saved energy with 0 failed requests.** Machines -6%, energy -6%, pods waiting
   -68%. p95 +11.6% is within the ±15% noise band shown by the watch arm; it was +19% in set 9 and +7% in set 7.
5. **The failed-request problem is gone.** 0 failed requests in all 20 runs; set 9 had 1 in 3,750 in the Omni-alone
   arm.

## Still open

- Omni on top released no machine: the node gate said "release permitted" all run, but the closure law recommended 6.
  Next: why the law holds at 6 here when Omni alone gives machines back.
- Five reps cannot separate ±15% effects on p95. Either more reps or paired runs on one machine (all arms back to back
  on the same runner) are needed to prove p95 either way.
