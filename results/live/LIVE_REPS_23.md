# Set 23 on real Kubernetes: set 22 repeated on the current code, ten paired repetitions, equal work

Run: benchmark-reps 36940088922, on `main` at the release with realm round 2 (`6475bea`). Same protocol as set 22:
- open-loop load at a fixed rate (`loadgen=open`), so both arms were sent the same work;
- 10 paired repetitions, each arm 15 minutes on kind (1 control plane, 6 workers), both arms of a repetition on one
  runner, order rotated.

Recomputed from the run's own raw files by `.github/workflows/reaggregate.yml`:
`results/live/reaggregated/LIVE_REPS_36940088922.md`.

| Gauge | Native | Omni on top | Change | 95% interval | Verdict | Set 22 |
|---|---:|---:|---:|---:|---|---:|
| response time, 95th percentile (ms) | 327.3 | 123.8 | **−62.2%** | −264.5 to −142.5 | better, proven | −61.1% |
| response time, 99th percentile (ms) | 503.4 | 169.3 | −66.4% | −431.2 to −237.0 | better, proven | −61.7% |
| response time, mean (ms) | 146.6 | 80.1 | −45.4% | −88.7 to −44.4 | better, proven | −45.3% |
| failed requests (%) | 0 | 0 | 0 | 0 to 0 | equal | 0 |
| HPA replicas, mean | 8.51 | 5.40 | −36.6% | −4.03 to −2.20 | fewer, proven | −22.7% |
| worker nodes in service, mean | 6 | 4.28 | −28.7% | −2.20 to −1.25 | fewer, proven (all stayed powered) | −31.0% |
| pods started | 4.7 | 1.7 | −63.8% | −4.22 to −1.78 | fewer, proven | not proven |
| pod start wait, total (s) | 18.6 | 3.8 | −79.6% | −21.2 to −8.4 | better, proven | not proven |
| CPU used, service and Omni together (cores) | 0.903 | 0.894 | −1.0% | −0.022 to +0.003 | **no difference** | −0.9% |
| energy, parked workers still on at idle power (Wh, declared model) | 159.0 | 158.7 | **−0.2%** | −0.78 to +0.21 | **no difference** | −0.1% |
| energy, parked workers at 25 W standby (Wh, declared model; kind never does this) | 159.0 | 126.1 | −20.7% | −42.0 to −23.9 | model only | −22.1% |

## Plainly

- **Set 22 reproduces on today's code, a week later, on fresh machines.** p95 is −62% (set 22: −61%), with no failed
  requests. Replicas are now 37% fewer, and pod starts and their wait are now proven lower.
- **There is still no energy saving on kind.** Every worker stays powered, so modelled energy is unchanged (−0.2%).
  Counting Omni's own CPU, total CPU is unchanged too (−1.0%, not proven).
- **The closed-loop work estimate printed under the recomputed table does not apply.** The load is fixed-rate, so
  both arms were sent the same requests.
