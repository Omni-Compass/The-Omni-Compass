# Set 18 on real Kubernetes: native against me on top; the autoscaler alone makes pods

Run: benchmark-reps 36358460215, commit f5bff2b. Five paired repetitions, 15 minutes each, kind with 1 control plane
and 6 workers. I gauge the queue and write no replica floor; the target I hold uses the CPU each pod is guaranteed.

A change is significant when its paired 95% interval excludes zero. Lower response time is better.

| Gauge | Native | Me on top | Verdict |
|---|---:|---:|---|
| workers in service, mean | 6 | 4.92 | −18.0%, better, significant |
| node-hours | 1.517 | 1.244 | −18.0%, better, significant |
| energy (Wh) | 158.9 | 140.8 | −11.3%, better, significant |
| energy per unit of work (Wh per core-hour) | 722 | 503 | −30.3%, better, significant |
| work done (CPU used, cores) | 0.874 | 1.125 | +28.7%, better, significant |
| replicas, mean | 8.89 | 6.73 | −24.3%, better, significant |
| response time, mean (ms) | 129.9 | 83.7 | −35.6%, better, significant |
| response time, 95th percentile (ms) | 267.4 | 126.9 | −52.6%, better, significant |
| response time, 99th percentile (ms) | 371.5 | 170.9 | −54.0%, better, significant |
| failed requests (%) | 0 | 0 | equal |
| pods not yet running, pod-minutes | 0.203 | 0.52 | +156%, not significant (set 17: +365%, significant) |

## What the trail shows (repetition 1)

- **Pod reflex:** no writes; it gauged only.
- **Pods:** the autoscaler ran 24% fewer pods than native, each with more CPU.
- **Machines:** I closed five of six to new work by the sixth decision. They idle as their pods leave, so machines in
  service fell by 18%, against 36% in sets 15–17, where the extra pod churn also emptied them faster.
