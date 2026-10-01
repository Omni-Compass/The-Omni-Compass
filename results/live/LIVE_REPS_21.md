# Set 21 on real Kubernetes: native against me on top, ten paired repetitions

Run: benchmark-reps 36466558583, commit 9e64f7b (conveyance only when response time needs it: `--convey-on 0.5`,
`--convey-off 0.25` of the 500 ms SLO). Ten paired repetitions, each arm 15 minutes on kind (1 control plane, 6 workers),
order rotated, both arms of a repetition on one runner. The table was recomputed from the run's own raw files by
`.github/workflows/reaggregate.yml` (run 36485672281) with the current `tools/live_reps.py`:
`results/live/reaggregated/LIVE_REPS_36466558583.md`. Artifact digests are in `RELEASE_MANIFEST.json`.

## What was measured

| Gauge | Native | Me on top | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| response time (ms), mean | 151.9 | 107.5 | −29.2% | −55.45 to −33.36 | better, proven |
| response time (ms), 95th percentile | 304.9 | 191.4 | −37.2% | −148.4 to −78.55 | better, proven |
| response time (ms), 99th percentile | 438.1 | 298.7 | −31.8% | −191.3 to −87.37 | better, proven |
| failed requests (%) | 0 | 0 | 0 | 0 to 0 | equal |
| HPA replicas, mean | 8.942 | 7.844 | −12.3% | −1.616 to −0.581 | fewer, proven |
| worker nodes in service, mean | 6 | 4.745 | −20.9% | −1.524 to −0.986 | fewer, proven (all stayed powered) |
| CPU used by the app (cores), mean | 0.911 | 1.146 | +25.8% | +0.171 to +0.300 | more, proven |
| pods started | 4.6 | 6.3 | +37.0% | −0.117 to +3.517 | not proven |
| pod start wait, total (s) | 10.2 | 17 | +66.7% | −1.98 to +15.58 | not proven |
| pending pods, pod-minutes | 0.105 | 0.355 | +238% | −0.074 to +0.574 | not proven |

## Energy: a declared model, not a meter

| Gauge | Native | Me on top | Change | 95% interval | Verdict |
|---|---:|---:|---:|---:|---|
| **energy, parked workers still on at idle power (Wh)**: what kind does | 159 | 161.9 | **+1.8%** | +2.13 to +3.65 | **worse, proven** |
| energy, parked workers at 25 W standby (Wh): needs a node autoscaler that removes the machine; this run has none | 159 | 138 | −13.2% | −26.16 to −15.72 | model only |

## Plainly

- **Response times are clearly better** (p95 −37%), with no failed requests.
- **This set does not show an energy saving.** Every worker stayed powered, and counted at the idle power it really
  draws, the modelled energy is 1.8% higher with me on top. The −13% figure holds only if a parked worker drops to
  25 W, which kind never does.
- **CPU use is 26% higher.** The load is closed-loop, so faster answers bring more requests (addendum below).
- Pod starts and waits did not differ significantly.

## Addendum: the load is closed-loop

The load generator waits for each answer before sending the next, so faster answers mean more requests: the CPU +26%
includes more work served. This set's own estimate (`tools/closed_loop_estimate.py` on its raw files, run by GitHub:
`results/live/reaggregated/CLOSED_LOOP_ESTIMATE_36466558583.json`):

| Gauge (estimated: the generators do not count their requests) | Change with me on top | 95% interval |
|---|---:|---:|
| requests served | **+28.2%** | +21.5% to +34.9% |
| CPU used | +25.5% | +18.4% to +32.5% |
| CPU per request | −2.1% | −5.3% to +1.1% (not proven) |
| energy per request (energy row "still on at idle power" ÷ requests; both a model and an estimate) | about −21% | not computed per repetition |

Work per energy stated without an estimate needs equal work; the next set runs a fixed-rate load (`LOADGEN=open`).
