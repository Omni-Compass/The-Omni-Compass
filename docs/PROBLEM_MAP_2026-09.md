# Problem map: what is broken in computing, and where Omni-Compass fits (September 2026)

Method: the issue trackers of the projects that run the world's clusters (Kubernetes autoscaler, Karpenter, Kepler,
Kueue, Volcano, Knative, KEDA, kubernetes/kubernetes), the public industry reports (Cast AI, Datadog, Uptime Institute,
IEA) and recent papers (Meta Llama 3, AI-datacenter power stabilisation). Not all of GitHub: a targeted scan of where
the money and the failures are. Status: **have** = in this repository and tested; **partial** = built but not proven
live; **missing** = not built.

| # | Problem (evidence) | Size | Best tool today and its gap | Omni-Compass fit | Status |
|---|---|---|---|---|---|
| 1 | **Idle capacity.** Average Kubernetes CPU utilisation 8%, memory 20%, falling; CPU over-provisioning 69%, memory 79% (Cast AI 2026). 83% of container cost goes to idle resources (Datadog) | largest money leak in cloud | Karpenter, Cluster Autoscaler, CAST AI: each fixes nodes only | one authority over replicas, requests, nodes and power | have (nodes, HPA); **missing: memory/request right-sizing muscle** |
| 2 | **HPA and VPA cannot be used together on CPU/memory**, "not compatible by design" (kubernetes/autoscaler #1726, #2939, #6060, #6247; coordination asked again in #8493, 2025) | blocks right-sizing for most teams | none; official advice is "don't" | exactly what a single authority solves: one engine owns both numerator and denominator | **missing: VPA-style request muscle under the same engine** (highest-value gap) |
| 3 | **Karpenter consolidation churn**: nodes replaced every 5-10 minutes for 2-3 generations, busy nodes removed instead of empty ones, one shared timer (karpenter #1851, #1019, #2705, #3046; provider-aws #7146, #8868, #7356, #8536) | outages, wasted boots | Karpenter's own timers and budgets | engine-gated release (equation 2) plus dwell; C-throughput cut node churn 50% in simulation | partial (sim); **live Karpenter opponent missing** |
| 4 | **CPU limits throttle apps** (CFS quota), causing latency and even OOMs (kubernetes/kubernetes #67577, #97445) | latency tails | manual tuning, "remove limits" advice | power-cap muscle must watch latency; our first live run hit this exact problem | have (fix wired: latency nerve plus usage reflex), live re-run pending |
| 5 | **Cold starts / scale-from-zero latency** (knative/serving #4902, #14202, #9104; kedacore/http-add-on #219) | seconds of latency per edge | Knative activator, KEDA | pre-warming decided by the engine from its state (anticipation) | **missing** |
| 6 | **GPU utilisation ~5%** (Cast AI 2026); idle GPUs scattered across nodes (volcano #3948, kueue #5243) | the most expensive silicon idle | KAI Scheduler, HAMi, nvshare, Volcano binpack | GPU power-limit muscle (have, calibrated), packing and sharing (missing) | partial: power limit have; **packing/fragmentation muscle missing** |
| 7 | **AI training power swings**: 50-75% of TDP in milliseconds per GPU, ramps over 1000 MW/s at gigawatt scale; operators impose power and ramp-rate limits (SemiAnalysis; Uptime; arXiv 2508.14318, 2606.04869) | grid-connection risk, equipment damage | batteries, fast PSUs, manual GPU power caps | "training power smoothing" muscle: ramp-rate limit through GPU power caps, the engine's bath state B is literally a damped oscillator | **missing** (highest strategic value) |
| 8 | **GPU failures and stragglers**: Llama 3, 419 interruptions in 54 days on 16K H100s, one every ~3 hours; 58.7% GPU-related; slow stragglers undetected (Meta; Lablup 2605.09370) | lost training time | Meta's internal tools, checkpointing | hardware-health muscle: sense straggling, drain early | **missing** |
| 9 | **Outages**: 54% cost more than $100,000, 1 in 5 more than $1M; power causes 45% of incidents (Uptime 2025) | direct money | SRE runbooks, AIOps | recovery and physical-SLA results in simulation: recovery 58 to 17 min | have (sim) |
| 10 | **Cooling**: industry PUE stuck at ~1.54 for six years (Uptime 2025) | ~35% overhead on every watt | DCIM, DeepMind cooling AI | heat afferent have; cooling-plant muscle missing | partial |
| 11 | **Energy measurement in VMs is impossible**: no RAPL/IPMI in VMs, Kepler building a model server (kepler #2487, 2026) | nobody can prove savings in cloud VMs | Kepler estimators | same gap we hit; Omni needs a declared model or metal | partial (declared model) |
| 12 | **LLM inference autoscaling**: KV cache fills memory before compute; prefill vs decode need separate scaling (vLLM, llm-d) | latency and GPU cost | llm-d, KServe, custom | inference muscle: scale on KV-cache use and queue, not CPU | **missing** |
| 13 | **Runaway AI agents**: loops and recursive calls, ~$10,000 overnight examples (Dark Reading; sandbox guides) | cost and safety | per-tool caps, early kill-switch projects | agent-containment muscle: caps, kill, audit (Omni already has kill and audit) | **missing** |
| 14 | **Human error**: failures to follow procedures rose 10 points (Uptime 2025) | outages | runbooks | fewer manual actions: pages and human interventions to zero in simulation | have (sim) |

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
