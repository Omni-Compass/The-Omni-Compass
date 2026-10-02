# Local run, 27 September 2026 (this build machine)

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../../LICENSE).

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
