# Problem map: what is broken in computing, and where Omni-Compass fits (September 2026)

Method: the issue trackers of the projects that run the world's clusters (Kubernetes autoscaler, Karpenter, Kepler,
Kueue, Volcano, Knative, KEDA, kubernetes/kubernetes), the public industry reports (Cast AI, Datadog, Uptime Institute,
IEA) and recent papers (Meta Llama 3, AI-datacenter power stabilisation). Not all of GitHub: a targeted scan of where
the money and the failures are. Status: **have** = in this repository and tested; **partial** = built but not proven
live; **missing** = not built.

| # | Problem (evidence) | Size | Best tool today and its gap | Omni-Compass fit | Status |
|---|---|---|---|---|---|
| 1 | **Idle capacity.** Average Kubernetes CPU utilisation 8%, memory 20%, falling; CPU over-provisioning 69%, memory 79% (Cast AI 2026). 83% of container cost goes to idle resources (Datadog) | largest money leak in cloud | Karpenter, Cluster Autoscaler, CAST AI: each fixes nodes only | one authority over replicas, requests, nodes and power | **built** (omnilab/rightsize.py, held-out) |
| 2 | **HPA and VPA cannot be used together on CPU/memory**, "not compatible by design" (kubernetes/autoscaler #1726, #2939, #6060, #6247; coordination asked again in #8493, 2025) | blocks right-sizing for most teams | none; official advice is "don't" | exactly what a single authority solves: one engine owns both numerator and denominator | **built** (omnilab/rightsize.py: HPA+VPA vs one authority, held-out) |
| 3 | **Karpenter consolidation churn**: nodes replaced every 5-10 minutes for 2-3 generations, busy nodes removed instead of empty ones, one shared timer (karpenter #1851, #1019, #2705, #3046; provider-aws #7146, #8868, #7356, #8536) | outages, wasted boots | Karpenter's own timers and budgets | engine-gated release (equation 2) plus dwell; C-throughput cut node churn 50% in simulation | built in simulation (AKS NAP = Karpenter arm, tuning/vendor_compare.py); live Karpenter opponent next |
| 4 | **CPU limits throttle apps** (CFS quota), causing latency and even OOMs (kubernetes/kubernetes #67577, #97445) | latency tails | manual tuning, "remove limits" advice | power-cap muscle must watch latency; our first live run hit this exact problem | have; live runs 3-5 found and fixed the resize permission |
| 5 | **Cold starts / scale-from-zero latency** (knative/serving #4902, #14202, #9104; kedacore/http-add-on #219) | seconds of latency per edge | Knative activator, KEDA | pre-warming decided by the engine from its state (anticipation) | **built** (omnilab/coldstart.py, held-out) |
| 6 | **GPU utilisation ~5%** (Cast AI 2026); idle GPUs scattered across nodes (volcano #3948, kueue #5243) | the most expensive silicon idle | KAI Scheduler, HAMi, nvshare, Volcano binpack | GPU power-limit muscle (have, calibrated), packing and sharing (missing) | **built** (omnilab/gpupack.py, held-out) + power limit |
| 7 | **AI training power swings**: 50-75% of TDP in milliseconds per GPU, ramps over 1000 MW/s at gigawatt scale; operators impose power and ramp-rate limits (SemiAnalysis; Uptime; arXiv 2508.14318, 2606.04869) | grid-connection risk, equipment damage | batteries, fast PSUs, manual GPU power caps | "training power smoothing" muscle: ramp-rate limit through GPU power caps, the engine's bath state B is literally a damped oscillator | **built** (omnilab/powersmooth.py, held-out; basin-only arm recorded) |
| 8 | **GPU failures and stragglers**: Llama 3, 419 interruptions in 54 days on 16K H100s, one every ~3 hours; 58.7% GPU-related; slow stragglers undetected (Meta; Lablup 2605.09370) | lost training time | Meta's internal tools, checkpointing | hardware-health muscle: sense straggling, drain early | **built** (omnilab/health.py, held-out) |
| 9 | **Outages**: 54% cost more than $100,000, 1 in 5 more than $1M; power causes 45% of incidents (Uptime 2025) | direct money | SRE runbooks, AIOps | recovery and physical-SLA results in simulation: recovery 58 to 17 min | have (sim) |
| 10 | **Cooling**: industry PUE stuck at ~1.54 for six years (Uptime 2025) | ~35% overhead on every watt | DCIM, DeepMind cooling AI | heat afferent have; cooling-plant muscle | **built** (omnilab/cooling.py, held-out) |
| 11 | **Energy measurement in VMs is impossible**: no RAPL/IPMI in VMs, Kepler building a model server (kepler #2487, 2026) | nobody can prove savings in cloud VMs | Kepler estimators | same gap we hit | **built** (omnilab/vmenergy.py: meter-calibrated attribution, held-out) |
| 12 | **LLM inference autoscaling**: KV cache fills memory before compute; prefill vs decode need separate scaling (vLLM, llm-d) | latency and GPU cost | llm-d, KServe, custom | inference muscle: scale on KV-cache use and queue, not CPU | **built** (omnilab/inference.py, held-out) |
| 13 | **Runaway AI agents**: loops and recursive calls, ~$10,000 overnight examples (Dark Reading; sandbox guides) | cost and safety | per-tool caps, early kill-switch projects | agent-containment muscle: caps, kill, audit | **built** (omnilab/containment.py, held-out); live version next |
| 14 | **Human error**: failures to follow procedures rose 10 points (Uptime 2025) | outages | runbooks | fewer manual actions: pages and human interventions to zero in simulation | have (sim) |

## Results of the build pass (held-out seeds 90001-90030, 30 per muscle, code frozen by SHA first)

Omni-Compass against the strongest native tool in each muscle; + better, - worse, = tie / not significant.

| # | Muscle | Opponent (best native) | Better | Worse | Tie / n.s. |
|---|---|---|---|---|---|
| 1-2 | right-sizing | VPA in-place + HPA | CPU -3%, memory -11%, p99 -99%, reversals -84%, SLO minutes -57% | p95 +15%, OOM kills (few) | work done |
| 5 | cold start | KEDA HTTP | p95 -75%, p99 -58%, delayed >1 s -71%, instance-hours -8% | cold-start count (x8) | |
| 6 | GPU packing | Volcano binpack | idle powered GPU-hours -20%, energy -2% | mean wait +16% (seconds) | p95 wait, jobs, fragmentation |
| 7 | training power | vendor floor, worst-day setting | burn -9%, throughput loss -44%, 1-s swing -6% | max ramp (inside the grid's limit) | 0 grid violations both |
| 8 | GPU health | threshold detection | goodput +10%, lost GPU-h -20%, restarts -29%, straggler hours -99% | | checkpoint overhead |
| 10 | cooling | outdoor-air reset | PUE -2%, cooling -13%, inlet violations -73% | | max inlet |
| 11 | VM energy | host meter split by CPU | per-VM error -37%, worst VM -34% | | total |
| 12 | LLM inference | KEDA on queue | TTFT p95 -18%, SLO breaches -58%, GPU-hours -19%, preemptions -56% | | TPOT, TTFT p50 |
| 13 | agent containment | static caps | rogue spend -96%, time to contain -99%, peak sub-agents -59% | false stops (0.6 -> ~2.7/day), honest work -7% | forbidden actions (0 both: RBAC) |

Engine vs no-engine: in every muscle the omni_no_engine arm scores close to omni. The mapping from engine state to
action carries most of the effect; the evolved dynamics add smoothing. The basin-only arm (power smoothing, the bath
equation alone setting the draw) cut ramps 63% but did not hold the grid limit: the human-set limit is required.

## What this says

- The problems with the most money behind them are **idle capacity (1)**, **HPA/VPA coordination (2)** and **GPU
  idleness (6)**. Problem 2 is the cleanest proof of Omni-Compass's thesis: the Kubernetes project itself says its two
  autoscalers cannot share a metric, because they fight. A single engine owning both is the answer the issue tracker
  keeps asking for.
- The problem with the most strategic weight is **AI training power swings (7)**: it is new, it threatens grid
  connections, and Omni-Compass's own equation (7) is a damped second-order bath, the natural controller for ramp limits.
- The problems we already hit ourselves (4, 11) are the same ones the industry has: good evidence the benchmark is real.

## Build order proposed

1. Request right-sizing muscle (VPA role) under the same engine, benchmarked against HPA + VPA "in conflict".
2. Training power-smoothing muscle (GPU power-cap ramp limits) with a synthetic synchronized-training power trace.
3. GPU packing / fragmentation muscle (with fake-gpu-operator or KWOK on the live cluster).
4. Live Karpenter opponent (kwok provider) to test problem 3 head to head.
5. Inference muscle (KV-cache and queue driven), then hardware-health (straggler drain), then agent containment.

## Sources

- kubernetes/autoscaler issues [#1726](https://github.com/kubernetes/autoscaler/issues/1726), [#2939](https://github.com/kubernetes/autoscaler/issues/2939), [#6060](https://github.com/kubernetes/autoscaler/issues/6060), [#6247](https://github.com/kubernetes/autoscaler/issues/6247), [#8493](https://github.com/kubernetes/autoscaler/issues/8493)
- Karpenter [#1851](https://github.com/kubernetes-sigs/karpenter/issues/1851), [#1019](https://github.com/kubernetes-sigs/karpenter/issues/1019), [#2705](https://github.com/kubernetes-sigs/karpenter/issues/2705), [#3046](https://github.com/kubernetes-sigs/karpenter/issues/3046); aws/karpenter-provider-aws [#7146](https://github.com/aws/karpenter-provider-aws/issues/7146), [#8868](https://github.com/aws/karpenter-provider-aws/issues/8868), [#7356](https://github.com/aws/karpenter-provider-aws/issues/7356), [#8536](https://github.com/aws/karpenter-provider-aws/issues/8536)
- kubernetes/kubernetes [#67577](https://github.com/kubernetes/kubernetes/issues/67577), [#97445](https://github.com/kubernetes/kubernetes/issues/97445)
- Knative [#4902](https://github.com/knative/serving/issues/4902), [#14202](https://github.com/knative/serving/issues/14202), [#9104](https://github.com/knative/serving/issues/9104); KEDA http-add-on [#219](https://github.com/kedacore/http-add-on/issues/219)
- Volcano [#3948](https://github.com/volcano-sh/volcano/issues/3948); Kueue [#5243](https://github.com/kubernetes-sigs/kueue/issues/5243); [KAI Scheduler](https://github.com/kai-scheduler/KAI-Scheduler); [HAMi](https://github.com/project-hami/hami)
- Kepler [#2487](https://github.com/sustainable-computing-io/kepler/issues/2487)
- [Cast AI 2026 State of Kubernetes Resource Optimization](https://cast.ai/blog/2026-state-of-kubernetes-resource-optimization-cpu-at-8-memory-at-20-and-getting-worse/); [Cloud Native Now on the report](https://cloudnativenow.com/features/report-utilization-of-kubernetes-infrastructure-remains-abysmal/)
- [Uptime Institute annual outage analysis 2025](https://uptimeinstitute.com/about-ui/press-releases/uptime-announces-annual-outage-analysis-report-2025); [Uptime global survey 2025](https://datacenter.uptimeinstitute.com/rs/711-RIA-145/images/2025.Annual.Survey.Report.pdf?version=0)
- [SemiAnalysis: AI training load fluctuations](https://newsletter.semianalysis.com/p/ai-training-load-fluctuations-at-gigawatt-scale-risk-of-power-grid-blackout); [Uptime: AI power fluctuations](https://journal.uptimeinstitute.com/ai-power-fluctuations-strain-both-budgets-and-hardware/); [Power Stabilization for AI Training Datacenters](https://arxiv.org/pdf/2508.14318); [Source-side mitigation](https://arxiv.org/pdf/2606.04869)
- [The Llama 3 Herd of Models](https://arxiv.org/pdf/2407.21783); [Tom's Hardware on Llama 3 failures](https://www.tomshardware.com/tech-industry/artificial-intelligence/faulty-nvidia-h100-gpus-and-hbm3-memory-caused-half-of-the-failures-during-llama-3-training-one-failure-every-three-hours-for-metas-16384-gpu-training-cluster); [Lablup 504-GPU report](https://arxiv.org/html/2605.09370v1)
- [vLLM anatomy](https://vllm.ai/blog/2025-09-05-anatomy-of-vllm); [llm-d 0.5](https://llm-d.ai/blog/llm-d-v0.5-sustaining-performance-at-scale)
- [Dark Reading: AI agents and runaway costs](https://www.darkreading.com/application-security/how-ai-agents-can-trigger-runaway-costs)
