# Local run, 27 September 2026 (this build machine)

**Real Kubernetes could not run pods on this build machine.** The sandbox forbids a negative `oom_score_adj`, and
Kubernetes sets -998 on every pod's sandbox container.

| Attempt | Result |
|---|---|
| kind (7 nodes) | nodes up; no pod could start |
| k3s on host Docker | node **Ready**; no pod could start |
| `docker run --oom-score-adj=-998` | fails the same way (proof of cause) |
| `docker run --oom-score-adj=0` | works |

**What ran here:**

| File | What it is |
|---|---|
| `CPP_BUILD.txt` | C++ engine build (Release) and CTest: 100% passed |
| `VERIFY_FULL*.txt` | the full verification suite |
| `NERVOUS_SYSTEM_DEMO.txt` | the live controller driven through five situations on the stand-in cluster (fake kubectl; no pods). It shows release, the latency hold, the blind-sense hold, the order-not-landed hold and the pods-first hold, each with its recorded reason. |

**To run live on real Kubernetes:** `bash RUN_LIVE.sh 3` on any machine with Docker, or a `[reps]` push to GitHub.
