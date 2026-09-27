# Omni-Compass: buyer edition

Commit 2f64761. Every number below is generated from result files in the repository by `python tools/buyer_report.py`. Simulated results use the repository's fleet plant; live results come from real Kubernetes (kind) in GitHub Actions. Competitors are reproduced from their public documentation, not their binaries.

## What Omni-Compass is

- **The engine:** a six-state control engine, stable by construction (every mode decays), in Python and C++.
- **The law it applies:** the closure law of the owner's manuscript.
  - It does nothing in the safe interior.
  - It corrects inward when the forecast approaches capacity.
  - It releases a machine only after the peak.
  - It keeps released machines warm for instant reuse.
- **What it governs:** machines, pod counts and sizes, cold start, batch pacing, containment of runaway agent workloads, and cooling setpoints.
- **Two ways to deploy it:**
  - **B, on top of the platform a customer already runs.** Nothing is replaced.
  - **C, alone.** Kubernetes stays only as the muscle; the scaling layer is replaced (HPA, Cluster Autoscaler, Karpenter, and optimizers such as CAST AI, Spot Ocean and Turbonomic).

## B: Omni-Compass on top of each platform (held-out scenarios, settings frozen first)

| Workload | Platform | Omni-Compass on top vs the platform alone |
|---|---|---|
| Web services | Kubernetes | scale reversals 12% better, machine starts+stops 2% better |
| Web services | OpenShift | scale reversals 44% better, machine starts+stops 4% better |
| Web services | GKE | scale reversals 21% better, machine starts+stops 7% better, machine-hours 3% better |
| Web services | AKS NAP / Karpenter | scale reversals 8% better, machine starts+stops 3% better |
| Web services | Turbonomic | scale reversals 8% better, machine starts+stops 2% better |
| Web services | CAST AI | slowest responses (p99) 34% better, scale reversals 30% better, machine starts+stops 15% better |
| Web services | Spot Ocean | slowest responses (p99) 42% better, scale reversals 34% better, machine starts+stops 17% better |
| Four clusters, one site | Kubernetes | scale reversals 93% better, slowest responses (p99) 51% better, machine starts+stops 21% better |
| Four clusters, one site | OpenShift | scale reversals 100% better, slowest responses (p99) 39% better, machine starts+stops 16% better |
| Four clusters, one site | GKE | slowest responses (p99) 38% better, scale reversals 19% better, machine starts+stops 11% better |
| Four clusters, one site | AKS NAP / Karpenter | scale reversals 7% better, slowest responses (p99) 6% better, machine starts+stops 4% better |
| Four clusters, one site | Turbonomic | scale reversals 4% better, machine starts+stops 2% better |
| Four clusters, one site | CAST AI | equal |
| Four clusters, one site | Spot Ocean | scale reversals 9% better, slowest responses (p99) 5% better, machine starts+stops 5% better |
| Batch jobs | Kubernetes | slowest responses (p99) 91% better, scale reversals 82% better, average response 25% better |
| Batch jobs | OpenShift | slowest responses (p99) 92% better, scale reversals 84% better, average response 26% better |
| Batch jobs | GKE | time over backlog limit 100% better, slowest responses (p99) 89% better, scale reversals 66% better |
| Batch jobs | AKS NAP / Karpenter | typical response (p95) 60% better, slowest responses (p99) 34% better, time over backlog limit 25% better |
| Batch jobs | Turbonomic | time over backlog limit 44% better, scale reversals 22% better, machine starts+stops 15% better |
| Batch jobs | CAST AI | time over backlog limit 100% better, typical response (p95) 94% better, slowest responses (p99) 91% better |
| Batch jobs | Spot Ocean | time over backlog limit 83% better, scale reversals 59% better, machine starts+stops 47% better |
| GPU training | Kubernetes | scale reversals 68% better, machine starts+stops 35% better |
| GPU training | OpenShift | scale reversals 61% better, machine starts+stops 29% better, time healthy 1% better |
| GPU training | GKE | scale reversals 59% better, machine starts+stops 39% better, machine-hours 1% better |
| GPU training | AKS NAP / Karpenter | machine starts+stops 51% better, scale reversals 33% better, machine-hours 2% better |
| GPU training | Turbonomic | scale reversals 12% better, machine starts+stops 9% better |
| GPU training | CAST AI | machine starts+stops 45% better, scale reversals 32% better, machine-hours 2% better |
| GPU training | Spot Ocean | machine starts+stops 28% better, scale reversals 21% better |

## C: Omni-Compass alone, one global setting, confirmatory run

- **Setting:** one global setting for every workload, frozen by SHA-256 before the run (28cbb82607cb0009).
- **Scenarios:** 100 never-used scenarios per workload (seeds 710001-710100).
- **Comparisons:** 364 cells (4 workloads x 7 platforms x 13 gauges).
- **Rule:** a cell counts as better or worse only if it survives Holm-Bonferroni correction across all 364 cells (family alpha 0.05) and exceeds the 0.5% practical tolerance. Otherwise it is equal.

**Result:** 153 better, 174 equal, 37 worse.

| Workload | Better | Equal | Worse | The worse cells |
|---|---:|---:|---:|---|
| Web services | 41 | 41 | 9 | Kubernetes typical response (p95) 20.7%; Kubernetes machine starts+stops 24.5%; OpenShift typical response (p95) 20.8%; OpenShift machine starts+stops 66.0%; OpenShift scale reversals 152.0%; GKE typical response (p95) 20.1%; AKS NAP / Karpenter typical response (p95) 19.7%; CAST AI typical response (p95) 19.2%; Spot Ocean typical response (p95) 19.7% |
| Four clusters, one site | 45 | 36 | 10 | Kubernetes typical response (p95) 20.4%; Kubernetes machine starts+stops 23.7%; OpenShift typical response (p95) 20.5%; OpenShift machine starts+stops 62.1%; OpenShift scale reversals 207.3%; GKE typical response (p95) 19.7%; AKS NAP / Karpenter typical response (p95) 19.3%; Turbonomic typical response (p95) 27.6%; CAST AI typical response (p95) 18.8%; Spot Ocean typical response (p95) 19.3% |
| Batch jobs | 35 | 50 | 6 | Kubernetes machine starts+stops 39.0%; OpenShift machine starts+stops 29.5%; AKS NAP / Karpenter energy 2.1%; CAST AI energy 1.2%; Spot Ocean energy 2.2%; Spot Ocean machine-hours 0.6% |
| GPU training | 32 | 47 | 12 | AKS NAP / Karpenter energy 1.0%; AKS NAP / Karpenter time over power limit 1.6%; AKS NAP / Karpenter time over heat limit 1.1%; CAST AI energy 1.0%; CAST AI time over power limit 3.2%; CAST AI time over heat limit 2.6%; CAST AI time healthy 1.6%; Spot Ocean energy 1.2%; Spot Ocean time over power limit 3.8%; Spot Ocean time over heat limit 1.8%; Spot Ocean machine-hours 1.4%; Spot Ocean time healthy 2.0% |

| Workload | Energy vs Kubernetes | Machine-hours | Slowest responses | Average response |
|---|---:|---:|---:|---:|
| Web services | +21% | +38% | +40% | +11% |
| Four clusters, one site | +25% | +40% | +41% | +13% |
| Batch jobs | +6% | +18% | +40% | +2% |
| GPU training | +2% | +11% | +0% | +0% |

Positive means Omni-Compass is better.

## Real demand: 1,052 recorded machines (PlanetLab)

- **Losing cells:** Omni-Compass alone, with the frozen web setting (never tuned on these traces), loses 0 of 91 against the seven platforms.
- **Whole-pod packing:** with whole-pod packing it loses 0 of 91.
- **Against Kubernetes:**
  - energy +24%
  - machine-hours +33%
  - typical response +97%
  - slowest responses +85%

Positive means better.

## Four-cluster sites as one body (held-out)

- **The mechanism:** traffic shift between clusters, plus the law run on the site total with one warm reserve.
- **Omni-Compass alone:** zero losing cells against GKE, AKS NAP / Karpenter, CAST AI, Spot Ocean.
- **Omni-Compass on top:** zero losing cells on all seven platforms.
- **Assumption:** services are replicated across the site's clusters.

## Under failure: the runtime protocol

Machines dying, load spikes, crash-looping services and noisy neighbours were injected at five stress levels, with identical faults for every system. Totals over all levels:

| Workload | System | Runs conveyed | Pages to a human | Recovery (min) |
|---|---|---:|---:|---:|
| Web services | CAST AI | 231 of 500 | 404 | 6.6 |
| Web services | Kubernetes | 218 of 500 | 338 | 8.3 |
| Web services | Omni-Compass alone | 240 of 500 | 246 | 5.1 |
| Four clusters, one site | CAST AI | 44 of 500 | 608 | 5.7 |
| Four clusters, one site | Kubernetes | 44 of 500 | 330 | 6.5 |
| Four clusters, one site | Omni-Compass alone | 46 of 500 | 197 | 3.6 |

## The supervisory nervous system

- **One state, every organ:** `omnicompass/nervous_system.py` turns the engine's state (convergence, basin health, stress against its equation-6 equilibrium, unmet need) into one calm value between 0 and 1.
- **Authority from calm:** calm grants each organ its authority:
  - pods and machines may give capacity back only above their reversibility thresholds (0.5 and 0.7);
  - CPU frequency, GPU power, routing and cooling get envelopes that widen with calm;
  - batch is admitted or paused;
  - rollback is authorised.
- **Holds and the shield:** a security hold stops every capacity organ from expanding. The shield stays downstream and can still veto.
- **Invariants tested:** 300,000 random engine states, with zero violations (`tests/test_nervous_system.py`).
- **Coordination:** pods move first, and a machine move opposite to the pod move is vetoed. Controller contradictions per day (fighting, or a reversal within one boot time):
  - web: 2.10 to 0.10;
  - four-cluster: 5.30 to 1.03, below Kubernetes' 2.10.

**Mechanism ablation** (`tuning/ABLATION.json`, fresh seeds 711001-711030): each part of the law removed in turn, against the full law. Listed: the gauges that get significantly worse (95% interval excludes 0, more than 0.5%).

| Part removed | Web services | Four clusters, one site | Batch jobs | GPU training |
|---|---|---|---|---|
| engine release gate removed | no change | no change | no change | no change |
| turning point removed | no change | machine starts+stops +2%, scale reversals +6% | slowest responses (p99) +32%, average response +12%, time over backlog limit +333%, machine starts+stops +47%, scale reversals +193%, contradictions +1350% | machine starts+stops +18%, scale reversals +118%, contradictions +1000% |
| muscle tone removed | typical response (p95) +1%, slowest responses (p99) +110%, average response +4%, machine starts+stops +92%, scale reversals +458%, contradictions +22% | slowest responses (p99) +8%, machine starts+stops +29%, scale reversals +108% | typical response (p95) +65%, slowest responses (p99) +151%, average response +26%, machine starts+stops +239%, scale reversals +1265%, machine-hours +1%, contradictions +875% | time over backlog limit +2%, machine starts+stops +297%, scale reversals +829%, contradictions +1150% |
| trend term removed | no change | slowest responses (p99) +2% | slowest responses (p99) +75%, average response +24%, time over backlog limit +533%, machine starts+stops +65%, scale reversals +348%, contradictions +2350% | machine starts+stops +29%, scale reversals +129%, contradictions +1100% |

## Live Kubernetes evidence

- **Earlier live sets 1 and 2:** these carried a probe defect, now fixed. The probe's one-pod tunnel hung when a drain moved its pod, so the Omni arms logged false failed requests (`results/live/LIVE_REPS_PROBE_DEFECT.md`).
- **What remains valid from them:** their machine counts. Omni-Compass on top ran 56% fewer workers than native, and Omni-Compass alone 50% fewer, both significant.

**Live levers under the nervous system:**

- **What acted:** right-sizing, cold start, batch pacing, agent containment and the cooling connector.
- **Authority:** each lever acted on real Kubernetes only inside the authority the nervous system granted.
- **Kill switch:** it restored every lever, including from a fresh process.
- **Result:** 19 of 19 checks passed (`results/live/LIVE_LEVERS_2_NERVOUS.txt`, first pass `LIVE_LEVERS_1.txt`).
- **Identity:** least-privilege, with `kubectl auth can-i` receipts.

**Shadow pilot kit, live:** a read-only identity ran for 600 s and logged 40 decisions, with 0 writes (`results/live/LIVE_SHADOW_1.txt`). This is the kit a customer runs first.

## Safety and correctness

- **Safety shield:** tested on 2,000,000 random and adversarial inputs, with zero invariant violations, idempotent, never inventing an action, and intervening minimally (`tests/test_shield_properties.py`). The test found two real bugs, both fixed.
- **C++ twins:** the C++ shield and the C++ closure law match Python exactly, over 300,000 adversarial shield cases and every recorded closure decision.
- **Endurance:** the C++ engine ran 100,000,000 decisions with no failure, at about 2.3 microseconds per decision.
- **Fail-safe:** after repeated failed decisions, control returns to the native autoscalers.
- **Reproducibility:** a clean copy of the delivered zip reproduced every held-out result byte for byte.

## What is not claimed

- **No production or customer deployment yet.** The next step is the shadow pilot (`docs/PILOT_KIT.md`), which is read-only.
- **Live runs are small.** They use kind on CI machines, and power is modelled, not metered.
- **Hardware levers are not proven.** CPU-frequency and power caps need real servers, and cooling was exercised against a stand-in controller.
- **Parked machines in the public cloud.** A parked cloud machine still bills, so the warm-reserve energy saving applies to owned hardware.
- **Single-cluster energy against the tightest packers is roughly a tie.** There Omni-Compass wins on response time and stability.
- **Some gaps cannot be closed.** No controller, even one with perfect foresight, can match both the tightest packer's machine-hours and the calmest autoscaler's machine churn (`tuning/bound.py`).
- **Not modelled in the plant:** variable boot times and pod-eviction cost. Fragmentation is modelled (whole-pod packing) and is small.

## Reproduce

```
pip install -r requirements.txt && python verify.py
python tuning/confirmatory.py        # C, one global setting, 100 scenarios per workload, Holm-corrected
python tuning/confirmatory.py --coord   # the same with nervous-system coordination, fresh seeds
python tuning/planetlab_league.py <planetlab-workload-traces/20110303>
python tuning/site_league.py --heldout
python tools/protocol_bench.py 100
live: push a commit whose message contains [reps], [levers] or [shadow]
```