# What this repository proves

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright and by patents and patent applications. See [`LICENSE`](LICENSE).

Labeled results only.

| Claim | Status in this tree |
|---|---|
| Engine equations stay finite; C++ matches Python fixtures | Proven by `verify.py` |
| Observe mode bit-identical to the in-tree Kubernetes *model* | Proven on held-out and fleet observe arms |
| Energy / health / churn on the **synthetic stack plant** | `results/heldout_seed_*` |
| Energy / health / churn on **PlanetLab-shaped demand** in `fleet/` | `results/fleet/planetlab/SUMMARY.json` (Omni as node pool, not as a sidecar-only target) |
| Documented HPA / CA *algorithm replica* | `fleet/harness.py`, `k8s_controlplane/` |
| Upstream kube-controller-manager / metrics-server binaries | **Not in this tree** |
| Live kind / EKS / GKE / AKS pilot | **Not in this tree** |
| Gigawatt campus or GPU scheduler replacement | **Not claimed** |

Simulation and recorded-trace replay are the product artifacts here.
Production SaaS and customer clusters are a licensed deployment, not a
README number.
