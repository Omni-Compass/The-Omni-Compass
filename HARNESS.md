# Omni-Compass full benchmark harness

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright and by patents and patent applications. See [`LICENSE`](LICENSE).

This tree is the GitHub-ready kit: frozen engine + C++ twin + two plants + live stub.

## What to run

```bash
pip install -r requirements.txt
python verify.py --quick          # engine, C++, soak, parity
python k8s_controlplane/test_controlplane.py
python -m k8s_controlplane.suite  # elastic / always_on / idle_power
python tests/test_hpa_three_way.py
python tests/test_omni_controller.py
```

Fleet plant (Omni as node authority vs HPA+CA / Karpenter-lite):

```bash
python -m fleet.planetlab --dir fleet/traces/planetlab --scenarios 8 --out /tmp/pl
```

C++:

```bash
cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release && cmake --build cpp/build -j2
./cpp/build/oc_smoke
```

## Two plants (do not mix the tables)

| Tree | What Omni is | What the energy number means |
|---|---|---|
| `k8s_controlplane/` | On top of HPA+CA (target / gate / park) | Pack and optional CA gate on a 20-node replica |
| `fleet/` | Node-pool authority; CA off | Consolidation vs CA and Karpenter-lite |

Observe must match the native arm on that plant. If it does not, the run is invalid.

## Engine species

Shipped `omnicompass/core.py` is the patent principal form: cubic \(U(1-U^2)\), FIG. 4 command, RK4 with held \(u\).
`omnicompass/pools.py` is actuation only (off / hold / park). It does not change the field.

## Not in this harness

Live kube-controller-manager, kind CI, GPU MIG scheduler, facility cooling plant.
`omni_controller/` is observe-first against kubectl; tests use `tests/fake_cluster/kubectl`.

See `LIMITS.md`.
