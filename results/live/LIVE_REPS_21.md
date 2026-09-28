# Set 21 on real Kubernetes: native against me on top, ten paired repetitions

Run: benchmark-reps 36466558583, commit 9e64f7b (conveyance only when response time needs it: --convey-on 0.5,
--convey-off 0.25 of the 500 ms SLO). Ten paired repetitions, each arm 15 minutes on kind (1 control plane, 6 workers),
order rotated. Aggregate from the run's own summary (tools/live_reps.py); raw files are the run's artifacts.

| Gauge | Native | Me on top | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.745 | -20.9% | -1.524 to -0.986 | yes, better |
| node-hours | 1.514 | 1.201 | -20.7% | -0.3815 to -0.2453 | yes, better |
| energy (Wh, declared model) | 159 | 138 | -13.2% | -26.16 to -15.72 | yes, better |
| response time (ms), mean | 151.9 | 107.5 | -29.2% | -55.45 to -33.36 | yes, better |
| response time (ms), 95th percentile | 304.9 | 191.4 | -37.2% | -148.4 to -78.55 | yes, better |
| response time (ms), 99th percentile | 438.1 | 298.7 | -31.8% | -191.3 to -87.37 | yes, better |
| failed requests (%) | 0 | 0 | +0 | +0 to +0 | no |
| pending pods, pod-minutes | 0.105 | 0.355 | +238.1% | -0.07431 to +0.5743 | no |
| CPU used (cores), mean | 0.911 | 1.146 | +25.8% | +0.1706 to +0.3002 | yes |
| HPA replicas, mean | 8.942 | 7.844 | -12.3% | -1.616 to -0.5808 | yes, better |
| pods started | 4.6 | 6.3 | +37.0% | -0.1174 to +3.517 | no |

Plainly:
- Conveyance only when needed did not bring CPU use down: +25.8%, the same as set 20 (+26.3%). The extra CPU is not
  from conveyance being on all the time; its source is still to be found.
- Response times are still clearly better (p95 -37%), a smaller gain than set 20 (-55%).
- Energy here is the declared model (no meter on kind), with a worker taken out of service counted at idle power; it is
  not a measurement.
