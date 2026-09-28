# Set 22 on real Kubernetes: native against Omni on top, ten paired repetitions, equal work

Run: benchmark-reps 36488547793, commit cfdc17c. Conveyance is on by default. The load is **open-loop at a fixed
rate** (`deploy/kind/loadgen-open.yaml`, 6 requests a second per generator, `LOADGEN=open`, confirmed in every job
log), so both arms were sent the same work.

- Ten paired repetitions, each arm 15 minutes on kind (1 control plane, 6 workers).
- Order rotated; both arms of a repetition on one runner.
- Recomputed from the run's own raw files by `.github/workflows/reaggregate.yml` with the current `tools/live_reps.py`
  (`results/live/reaggregated/LIVE_REPS_36488547793.md`).
- Artifact digests: `results/live/SET22_ARTIFACTS.json`.
- Mechanism: engine components F, C, h, G, dt identical to the release (`RELEASE_MANIFEST.json`).

## Energy first: a declared model, not a meter

| Gauge | Native | Omni on top | Change | 95% interval | Verdict |
|---|---:|---:|---:|---:|---|
| **energy, parked workers still on at idle power (Wh)**: what kind does | 160.3 | 160.1 | **−0.1%** | −0.67 to +0.41 | **no difference** |
| energy, parked workers at 25 W standby (Wh): needs a node autoscaler that removes the machine; this run has none | 160.3 | 124.8 | −22.1% | −42.8 to −28.1 | model only |

## CPU, with Omni's own cost counted

| Gauge | Native | Omni on top | Change | 95% interval | Verdict |
|---|---:|---:|---:|---:|---|
| CPU used by the service (cores) | 1.036 | 0.957 | −7.6% | −0.094 to −0.064 | less, proven |
| Omni's own CPU (the controller and every command it ran) | 0 | 0.070 | +0.070 | +0.063 to +0.076 | more, proven |
| **CPU used, service and Omni together** | 1.036 | 1.026 | **−0.9%** | −0.024 to +0.005 | **no difference** |

On equal work, the service itself used 7.6% less CPU. Omni's controller spent almost all of that. Together there is
no proven CPU saving.

## Service

| Gauge | Native | Omni on top | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| response time (ms), mean | 179.9 | 98.4 | −45.3% | −99.0 to −64.0 | better, proven |
| response time (ms), 95th percentile | 407.9 | 158.8 | **−61.1%** | −298.3 to −199.9 | better, proven |
| response time (ms), 99th percentile | 639.4 | 245.1 | −61.7% | −476.4 to −312.3 | better, proven |
| failed requests (%) | 0 | 0 | 0 | 0 to 0 | equal |
| pending pods, pod-minutes | 0.265 | 0.025 | −90.6% | −0.43 to −0.05 | better, proven |
| HPA replicas, mean | 8.93 | 6.91 | −22.7% | −2.70 to −1.35 | fewer, proven |
| worker nodes in service, mean | 6 | 4.14 | −31.0% | −2.26 to −1.47 | fewer, proven (all stayed powered) |
| pods started | 3.6 | 3.0 | −16.7% | −2.66 to +1.46 | not proven |
| pod start wait, total (s) | 12.3 | 5.6 | −54.5% | −15.9 to +2.5 | not proven |

## Plainly

- **Same work, much faster answers:** p95 −61%, p99 −62%, no failed requests, 91% less time with pods waiting,
  23% fewer replicas.
- **No energy saving is shown on kind.** Every worker stayed powered; counted at the idle power it really draws, the
  modelled energy is the same (−0.1%, not proven). The −22% figure holds only if a parked worker is really switched off.
- **No CPU saving once Omni's own cost is counted.** The service used 7.6% less CPU, and the controller used 0.07 cores
  to do it: together −0.9%, not proven. The controller's cost is the next thing to cut.
- The closed-loop work estimate printed at the foot of the recomputed page **does not apply** to this set: the load is
  fixed-rate, so both arms were sent the same requests.
- The generators do not record their own failures; the probe saw none in either arm.
- Kill switch: every setting restored in every repetition (target, CPU limits, replica range, all workers open to work).
