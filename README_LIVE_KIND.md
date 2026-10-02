# Live pilot on real Kubernetes in GitHub Actions

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright and by patents and patent applications. See [`LICENSE`](LICENSE).

Copy these files into the root of the Omni-Compass repository (the verified package, SHA-256 beginning 5a546370).
On every push, or from the Actions tab ("live-kind", Run workflow), GitHub starts a real Kubernetes cluster (kind),
installs metrics-server, deploys the official Kubernetes HPA walkthrough workload (registry.k8s.io/hpa-example) with
a CPU-based HPA and a load generator, then:

1. Phase A (10 min): HPA alone; the Omni-Compass controller in observe mode. The number of writes must be 0.
2. Phase B (10 min): the controller in target mode writes the HPA target.
3. Kill switch: the original HPA target (50) must be restored, or the run fails.
4. Both phases are scored with pilot/score.py; captures, audit logs and the score are uploaded as the
   "kind-pilot-results" artifact.

What this proves: the controller runs against a real Kubernetes control plane (real scheduler, real HPA, real
metrics-server), observe mode writes nothing, target mode writes bounded HPA targets, and the kill switch restores.
What it does not prove: energy or cost savings (kind nodes are containers on one virtual machine; the score uses a
declared power model). Node-pool mode is not exercised; it must not be used until scale-down cordons and drains
specific nodes.

Not yet run: this workflow was written and syntax-checked in an environment with no container runtime or network.
Its first run on GitHub is its first real execution.
