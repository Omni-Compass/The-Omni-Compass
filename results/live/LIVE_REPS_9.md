# Live set 9: kind, 7 nodes (6 workers), 5 paired reps per arm, 900 s each

Run: benchmark-reps 36309238960 on commit 5ae3f01 (set 8, run 36308670935, was cancelled before it finished;
this set replaces it). Aggregated with `tools/live_reps.py`.

Changes since set 7:
- Power and heat no longer veto a machine release.
- A released worker counts as removed from the pool (0 W, as in a cloud node pool), in every arm.
- The HPA target is queue-matched.

## B: Omni-Compass on top vs native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.3 | -11.7% | -1.891 to +0.4903 | no |
| node-hours | 1.511 | 1.334 | -11.7% | -0.4855 to +0.1312 | no |
| energy (Wh) | 166.8 | 148.5 | -11.0% | -50.12 to +13.53 | no |
| response time (ms), mean | 192 | 237.4 | +23.6% | -35.17 to +125.9 | no |
| response time (ms), 95th percentile | 378.9 | 482.8 | +27.4% | -16.98 to +224.8 | no |
| response time (ms), 99th percentile | 517.6 | 669.4 | +29.3% | -1.975 to +305.5 | no |
| failed requests (%) | 0 | 0 | +0 (native is 0) | +0 to +0 | no |
| pending pods, pod-minutes | 0.71 | 0.3933 | -44.6% | -0.9611 to +0.3278 | no |
| utilisation (used / allocatable) | 0.07394 | 0.08251 | +11.6% | -0.008004 to +0.02515 | no |

## C: Omni-Compass decides (strict) vs native

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.835 | -19.4% | -2.7 to +0.3698 | no |
| node-hours | 1.511 | 1.225 | -18.9% | -0.6791 to +0.1069 | no |
| energy (Wh) | 166.8 | 137.2 | -17.8% | -68.4 to +9.145 | no |
| response time (ms), mean | 192 | 221.5 | +15.4% | -71.21 to +130.2 | no |
| response time (ms), 95th percentile | 378.9 | 449.3 | +18.6% | -119.4 to +260.2 | no |
| response time (ms), 99th percentile | 517.6 | 626.5 | +21.0% | -113.9 to +331.6 | no |
| failed requests (%) | 0 | 0.02667 | +0.0267 (native is 0) | -0.04736 to +0.1007 | no |
| pending pods, pod-minutes | 0.71 | 0.3867 | -45.5% | -0.6121 to -0.03455 | yes, better |
| utilisation (used / allocatable) | 0.07394 | 0.0891 | +20.5% | -0.01632 to +0.04665 | no |

## Reading

Machines are now released live, and energy falls 11% (B) and 18% (C). With only 5 reps, neither drop is significant.
Response time went the wrong way in both arms. This set is not a win.

## Diagnosis from the decision trails (rep 1, both arms)

- All senses were live (no blind senses after the first decision), and drift was 0.
- Every time the SLO came back clean, the next decision breached:
  - B: 414.7 -> 597.6 ms, 464.4 -> 798.4 ms, 472.6 -> 550.2 ms
  - C: 413.0 -> 663.9 ms, 405.5 -> 727.9 ms
- A clean SLO is the only state in which Omni caps pod CPU (the power-cap muscle, CFS throttling) and raises the HPA
  target. The strict arm never touches the HPA target and shows the same pattern, so the power cap is the common cause.
- Why the cap is wrong for this workload: a request-served workload's CPU-seconds are set by its arrivals. Throttling
  runs the same work later, so it saves no energy and only adds queueing wait.
- Why the HPA target raise is wrong: for a fixed load, fewer pods always means a longer M/M/c wait, so no target above
  the operator's keeps the wait. The "queue-matched" raise (70% -> 79% at 2.4 busy pods) kept the same replica count,
  so it saved nothing and spent burst headroom.

## Fix (set 10)

- `omni_controller/muscles.py`: no power cap on a request-served workload (latency sense wired). Energy comes from
  machines.
- `omni_controller/controller.py`: Omni on top may tighten the HPA target but never loosen it.
