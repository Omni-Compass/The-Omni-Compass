# What this repository proves

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
