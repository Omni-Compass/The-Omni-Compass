# Omni-Compass compared with what runs data centers today

People who run these systems often see "autoscaling" everywhere and assume it all does the same thing. It does not.
This page sets out, from public descriptions, what each system controls, and where Omni-Compass sits among them.

**How to read it.** Borg and Twine are private to Google and Meta; Turbonomic is closed commercial software. None of
them can be run here, so they are compared by what their makers have published (papers, documentation, product
pages), never by a run. A mark of "—" means the capability is not in the system's public description, not that it
is impossible for it. The only fair measured comparison is on the customer's own system: their stack as it runs today
against the same stack with Omni-Compass on top, in paired runs (`docs/INTEGRATION_MANUAL.md`, section 6).

---

## 1. What each system controls

| System (public description) | Pods / replicas | Machines | GPU power | CPU clock / power | Moves watts between CPU and GPU | Site power budget | One decision across all of these |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Kubernetes HPA | ✓ | — | — | — | — | — | — |
| Kubernetes VPA | ✓ (requests) | — | — | — | — | — | — |
| Cluster Autoscaler, Karpenter | — | ✓ | — | — | — | — | — |
| KEDA | ✓ (to zero) | — | — | — | — | — | — |
| Red Hat OpenShift / OKD | ✓ (the Kubernetes autoscalers) | ✓ (machine autoscaling) | — | — | — | — | — |
| IBM Turbonomic | ✓ (sizing, scaling) | ✓ (placement, sizing) | — | — | — | — | partial (resource actions across layers) |
| Google Borg | ✓ (job scheduling) | ✓ (cluster placement) | — | — | — | Google has published separate power-capping work | — |
| Meta Twine | ✓ | ✓ | — | — | — | Meta has published separate power management (Dynamo) | — |
| NVIDIA DCGM | — | — | ✓ (limits, monitoring) | — | — | — | — |
| Linux schedutil, RAPL | — | — | — | ✓ | — | — | — |
| AMD SmartShift, NVIDIA Dynamic Boost (laptops) | — | — | ✓ | ✓ | ✓ (inside one laptop) | — | inside one device |
| Intel GEOPM (HPC) | — | — | partial | ✓ | partial (per job) | ✓ (per job / cluster) | partial |
| **Omni-Compass** | ✓ (on top of HPA; or deciding) | ✓ (park and wake) | ✓ | ✓ | ✓ (conveyance law; simulated) | ✓ (simulated) | ✓ |

## 2. How each one decides

| | Typical rule | Omni-Compass |
|---|---|---|
| Pods | add replicas when average CPU passes a target | the same autoscaler keeps working; Omni-Compass sets its target from the whole system's state and raises floors ahead of bursts |
| Machines | add when pods cannot be placed, remove when underused | park and wake machines by one law, and only when every sense is live, pods are not rising and nothing waits |
| GPU | vendor default: full power, or a fixed cap set by hand | a cap from the engine, bounded by a floor and released at once when the card is busy or response time slips |
| CPU | the kernel's governor picks a clock from recent load | a ceiling from the same engine, inside the nervous system's envelope |
| Power | a fixed plan leaving room for every device at peak; a breaker or capper reacts when the site goes over | one conserved budget: watts move from organs holding surplus to organs in need, never created, never over the budget |
| Safety | per tool | one OFF switch returns every organ to its recorded setting; watch mode first; service first |

## 3. What is different, in plain words

1. **One brain instead of many separate reflexes.** Today each tool watches its own gauge: the pod autoscaler watches
   CPU, the node autoscaler watches pending pods, the GPU runs at its default, the power plan is fixed on paper.
   Nobody decides for the whole. Omni-Compass reads the whole system into one state and tells each tool the envelope
   it may act in. The tools keep doing their own jobs.
2. **Power as a budget that moves.** Today a building keeps room for every device to hit its peak at once, so much of
   its power sits reserved and unused. Omni-Compass treats the building's watts as one conserved total and moves them
   to where the work is: from CPUs and quiet GPUs to busy GPUs, never over the limit (`docs/CONVEYANCE_LAW.md`).
3. **A proof, not a tuned dial.** The budget law is proved to conserve the budget and to converge, and those
   properties are checked on every build (`tests/test_conveyance.py`).
4. **Service guarded on every power move.** Power is only taken back while response time is inside the target, and
   given back at once when it is not.
5. **Reversible in one move.** Every setting is recorded before it is changed and restored by one switch.

## 4. What the numbers show today, and what kind they are

| Against | Result | Kind |
|---|---|---|
| Kubernetes as it runs by default (HPA + fixed nodes) | p95 response time −37% to −55%, replicas −12% to −25%, machines in service −17% to −21% | measured on real Kubernetes (kind), 10 paired runs each, `results/live/` |
| A GPU at its vendor default | +1.3% to +5.1% work per energy, p95 within +10% | modelled card (MLPerf-calibrated), `results/gpu/sim/after` |
| Today's power practice (every GPU at one fixed cap that leaves room for every CPU at peak) | +1.4% to +5.7% work served, backlog −16% to −28%, never over the site budget | modelled, `results/hardware/NODE_EXCHANGE_*.json` |
| A reactive site capper alone | 60-196 minutes over the site budget without Omni-Compass; 0 with it | modelled |

Turbonomic, Borg and Twine cannot be measured here. Against a customer who runs one of them, the comparison is made on
the customer's own system, with the same paired method.

## 5. Sources

- Kubernetes HPA, VPA, Cluster Autoscaler, Karpenter, KEDA: the projects' own documentation.
- Red Hat OpenShift / OKD: Red Hat's documentation of its autoscaling and machine management.
- IBM Turbonomic: IBM's product documentation.
- Borg: Verma et al., "Large-scale cluster management at Google with Borg", EuroSys 2015; Google's public Borg traces.
- Twine: Tang et al., "Twine: A Unified Cluster Management System for Shared Infrastructure", OSDI 2020.
- Meta Dynamo: Wu et al., "Dynamo: Facebook's Data Center-Wide Power Management System", ISCA 2016.
- NVIDIA DCGM and Dynamic Boost; AMD SmartShift; Intel GEOPM: the vendors' documentation.

Where a row above is wrong or out of date, correct it from the maker's own publication.
