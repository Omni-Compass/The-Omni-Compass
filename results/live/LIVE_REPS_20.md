# Set 20 on real Kubernetes: native against me on top, ten paired repetitions

Run: benchmark-reps 36366603505, commit 18220d4. Ten paired repetitions, each with native and me on top back to back on
one GitHub Actions runner, order rotated. Each arm is 15 minutes after a 120 s warm-up, on kind (Kubernetes in Docker)
with 1 control plane and 6 workers. The engine is the same as set 19; only the measurement changed:
- every pod start is now timed exactly, from the API server's own record of creation to Ready;
- ten repetitions instead of five.

A change is proven when its paired 95% interval excludes zero.

## The two columns

| Gauge | Native | Me on top | Change | 95% interval of the difference | Verdict |
|---|---:|---:|---:|---:|---|
| response time, mean (ms) | 126.1 | 79.4 | −37.1% | −59.6 to −34.0 | better, proven |
| response time, 95th percentile (ms) | 264 | 120 | −54.6% | −172.8 to −115.3 | better, proven |
| response time, 99th percentile (ms) | 374.9 | 154.4 | −58.8% | −256.9 to −184.2 | better, proven |
| failed requests (%) | 0 | 0 | 0 | 0 to 0 | equal |
| pods the autoscaler had to start | 4.9 | 2.6 | −46.9% | −3.92 to −0.68 | better, proven |
| pod start wait, total (s) | 13.8 | 7.1 | −48.6% | −13.26 to −0.14 | better, proven (narrowly) |
| pod start wait, mean per pod (s) | 2.73 | 1.48 | −45.9% | −2.28 to −0.23 | better, proven |
| pods not yet running, 15 s snapshots (pod-minutes) | 0.367 | 0.233 | −36.4% | −0.43 to +0.16 | better, not proven (coarse gauge) |
| replicas, mean | 8.82 | 6.57 | −25.5% | −2.95 to −1.55 | better, proven |
| workers open to new work, mean | 6 | 4.96 | −17.4% | −1.35 to −0.73 | fewer, proven (see below) |
| CPU burned by the app (cores) | 0.881 | 1.112 | +26.3% | +0.17 to +0.29 | more, proven (see below) |
| energy, idled worker at 25 W (declared model) | 158.7 | 141.2 | −11.0% | −23.6 to −11.5 | lower, proven, model only |
| energy, idled worker fully on at 100 W | 156.0 | 158.2 | +1.4% | +1.4 to +3.0 | **worse, proven** |

## What these numbers are, plainly

- **Measured and real:** response times, failed requests, pod starts and their waits, replicas. The load generator
  sent the same schedule to both columns.
- **Workers open to new work** counts workers not marked prefer-not. Every worker stayed powered and Ready in both
  columns. Fewer open workers saves nothing by itself; it is money only when a node autoscaler removes the idled
  machine.
- **CPU burned** is not more work done. The work was the same in both columns; the app was allowed to use its
  machine's spare CPU, so it burned more and answered faster.
- **Energy** has no meter on kind. The script declares 100 W per worker in use plus 150 W at full CPU, and an idled
  worker at 25 W. That 25 W is an assumption from the simulator. If an idled worker draws its full 100 W idle power
  (which it does while it stays on), I use **1.4% more** energy than native, and that is proven. Energy savings need a
  real meter and a machine that is actually removed; this set shows neither.

## The trail

In all ten repetitions the human switch drill after the run restored everything: HPA target 50, 6 of 6 workers open,
no Omni record left. The autoscaler alone made and removed every pod; no pod was moved, evicted or restarted.

## Raw files

`results/live/raw/run-36366603505/`, 333 files, checked by `SHA256SUMS_ALL.txt`. The table recomputes from them:
copy the `paired-*/bench-*` folders into one folder and run `python tools/live_reps.py <that folder>`. The 100 W energy
row adds 75 W × (6 − nodes_ready) to each 15 s interval of `capture.csv` in both columns.

## Addendum, 28 September 2026: the work was not the same

The sentence above, "The work was the same in both columns", is wrong. The load generator (`deploy/kind/loadgen.yaml`)
is closed-loop: each generator sends 20 requests one after another, each waiting for its answer, then pauses 0-2 s.
Faster answers therefore mean more requests. Estimated from each repetition's measured response time and the load
schedule (the generators do not log their own counts), with me on top the service answered about **35% more requests**
(95% interval +28% to +42%) with 26% more CPU, so **CPU per request was about 7% lower** (−9% to −5%). The energy rows
compare runs that served different amounts of work. A count of requests served, or an open-loop load at a fixed rate,
is needed to state work per energy; set 22 does that (`LOADGEN=open`).
