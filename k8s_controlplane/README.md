# Control-plane replica harness

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Referee-grade comparison of Omni-Compass against **documented** Kubernetes
control-plane algorithms, not against the original 5-minute synthetic stand-in
and not against live `kube-controller-manager`.

## What is in the loop

| Loop | Cadence | Algorithm replica |
|---|---|---|
| Metrics-server | 15 s scrape, 15 s lag | Ready-pod average of usage/request; new pods silent until readiness |
| HPA | 15 s | Official ratio law, 10% tolerance, 300 s scale-down max-in-window, scale-up `max(4 pods, 100%)` / 15 s |
| Cluster Autoscaler | 10 s | Pending-pod scale-up, request-utilization < 0.5 for 10 min, 10 min delay-after-add |
| Karpenter-lite | 15 s | Faster boot, pending provision, empty/underutilized consolidation + budget |
| Omni-Compass | 300 s | Same `Governor` / shield as the kit; writes HPA target and optionally nodes/power |

## Arms

- `hpa70_ca` / `hpa50_ca` / `hpa80_ca` — HPA + CA, static targets
- `hpa70_karpenter` — HPA + Karpenter-lite
- `omni_observe_hpa70_ca` — Omni computes, writes nothing (must match `hpa70_ca`)
- `omni_target_hpa70_ca` — Omni writes only `ρ*` into HPA.target
- `omni_target_down_hpa70_ca` — `ρ*` + Omni owns scale-down, CA keeps scale-up
- `omni_protect_full` / `omni_throughput_full` — target + nodes + power cap + shield

## What this still is not

- Not the upstream binaries
- Not a kube-scheduler / predicate-priority simulator
- Not PDBs, affinity, multi-AZ, local storage, system-pod skip
- Not Karpenter NodePool disruption controller
- Not production evidence

It is the strongest comparison that can be built without a cluster: same plant,
documented inner-loop algorithms, Omni as an outer loop at a realistic period.

```
python k8s_controlplane/test_controlplane.py
python -m k8s_controlplane.benchmark --scenarios 24 --seed 424242
```
