# Set 19 on real Kubernetes: native against me on top

Run: benchmark-reps 36362185876, commit d0ddb94. Five paired repetitions, each with native and me on top back to back
on one runner, order rotated. Each arm is 15 minutes (DURATION 900 s) after a 120 s warm-up, on kind v0.31.0 and
Kubernetes v1.35.0 with 1 control plane and 6 workers, metrics-server v0.9.0.

**What I do on top of the muscles:**
- **CPU:** each machine's idle CPU goes to the pods serving on it, in place, never below the operator's limit.
- **Autoscaler target:** I hold it in queue terms at the CPU each pod is guaranteed, for at least the autoscaler's
  own window (300 s).
- **Machines:** a machine I idle is marked prefer-not, and the one with the least work goes first.
- **Pods:** the autoscaler alone makes and removes them; my pod reflex gauges and writes nothing.

A change is significant when its paired 95% interval excludes zero. Lower response time is better.

## The two columns

| Gauge | Native | Me on top | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| workers in service, mean | 6 | 5.118 | −14.7% | −1.251 to −0.514 | better, significant |
| node-hours | 1.519 | 1.298 | −14.5% | −0.3156 to −0.1254 | better, significant |
| energy (Wh) | 158.7 | 143.9 | −9.3% | −22.87 to −6.793 | better, significant |
| energy per unit of work (Wh per core-hour) | 754.6 | 578.8 | −23.3% | −197.2 to −154.4 | better, significant |
| work done (CPU used, cores) | 0.8351 | 0.9923 | +18.8% | +0.05349 to +0.2608 | better, significant |
| utilisation (used / allocatable) | 0.0348 | 0.04832 | +38.9% | +0.01034 to +0.01672 | better, significant |
| replicas, mean | 8.726 | 5.49 | −37.1% | −4.044 to −2.428 | better, significant |
| response time, mean (ms) | 91.51 | 60.92 | −33.4% | −55.51 to −5.661 | better, significant |
| response time, 95th percentile (ms) | 201.5 | 92.49 | −54.1% | −147.8 to −70.16 | better, significant |
| response time, 99th percentile (ms) | 297.1 | 110.1 | −63.0% | −237.5 to −136.6 | better, significant |
| failed requests (%) | 0 | 0 | 0 | 0 to 0 | equal |
| pods not yet running, pod-minutes | 0.2633 | 0.16 | −39.2% | −0.6034 to +0.3968 | better, not significant |

Every gauge is better than native or equal to it. Ten of the twelve are better and significant. Failed requests are
zero in both columns. Pods not yet running is lower than native but not significant.

## The trail, repetition by repetition

Every repetition:
- 15 of 15 decisions, 0 failed decisions or checks.
- The human switch drill after the run restored everything:
  - pod CPU limits 500m;
  - HPA replica range 1,10;
  - HPA target 50;
  - 6 of 6 workers open;
  - no Omni record left.

| Repetition | Order | My writes | My own cost (cores) | HPA target writes | Idle order (first to go first) |
|---|---|---:|---:|---|---|
| 1 | native, then me | 18 | 0.051 | 190% → 127% | worker, 2, 3, 4, 5 (6 open) |
| 2 | me, then native | 15 | 0.050 | 190% → 95% | 2 (empty), worker, 3, 4, 5 (6 open) |
| 3 | native, then me | 18 | 0.070 | 190% → 127% | worker, 3, 4, 5, 6 (2 open) |
| 4 | me, then native | 18 | 0.079 | 190% → 127% | worker, 2, 3, 5, 6 (4 open) |
| 5 | native, then me | 15 | 0.051 | 190% → 95% | 2 (empty), worker, 3, 4, 5 (6 open) |

**Writes by muscle, every repetition:**
- 5 idle marks, one machine per decision, 6 → 1 open.
- 2 records of the original target.
- 2 HPA targets.
- 1 record of the original CPU limit.
- 5 to 8 CPU conveyances: 3700m for a pod alone on its machine, 1850m for two sharing one.
- Pod reflex: no writes.

**What the autoscaler did.**
- The first target (190%) came once response time had been clean for three decisions. The second came one full
  window later, when the machines in service had changed.
- There were no more than two target writes in any run.
- The replica floor was never touched: the autoscaler made and removed every pod.

**Decisions, repetition 1** (machines open → recommended, p95 ms, gate):

```
6 -> 6  119.8  node organ has no contraction authority (start)
6 -> 5   57.6  release permitted
5 -> 4   62.6  release permitted
4 -> 3   75.4  release permitted
3 -> 2   65.7  release permitted
2 -> 1   71.0  release permitted
1 -> 1   72.8 / 70.1 / 76.6 / 68.5 / 69.1 / 78.7 / 66.3 / 69.4 / 65.5  one machine left
```

**The compass across the run:** Β (peak extension) → Α (rising through rest) → Ε → Κ/Μ/Λ (dispersion, the ceiling
holds) → Ν (falling through rest). Ω held and G·n ≤ 0 at every decision. The composite ledger fell from 868 to 662 while
the machines idled, then rose by at most 5 in the last decisions as the load stepped.

## Raw files

Every file of every repetition is in `results/live/raw/run-36362185876/`, 118 files. Each `paired-N/bench-<arm>-N/`
holds:
- the capture every 15 s (`capture.csv`) and the response-time probe (`latency.csv`);
- my audit of every read, write and compass reading (`audit.jsonl`) and my controller log;
- the human switch drill (`kill_switch.txt`, `audit_kill.jsonl`);
- the identity receipts, the load schedule and the cluster's end state;
- a SHA-256 manifest.

`SHA256SUMS_ALL.txt` covers all of them. The table above recomputes exactly from these files:
`python tools/live_reps.py <folder holding the bench-* folders>`.
