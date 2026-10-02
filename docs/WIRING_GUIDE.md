# Wiring Omni-Compass into your Kubernetes

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

> **Before you wire anything:** read [`DISCLOSURES.md`](../DISCLOSURES.md). Omni-Compass acts only through the wires it is given; it cannot be slapped on. If your paired receipts differ from the published benchmarks in direction, the first presumption is wiring: confirm the installation with section 8.5 of the manual (*Wired right or wired wrong*).

> **The current manual is `docs/INTEGRATION_MANUAL.md`** (every stack, every level, every switch). This page is kept for
> reference; where the two differ, the integration manual is current.

> The full step-by-step manual, with the switch, the living band, parking and the pod reflex, is
> `docs/OPERATOR_MANUAL.md`. This page is the short version.

**Three stages.** Each stage adds only the permissions it needs. A stage is promoted only after its evidence is in,
and the kill switch works at every stage:

```
kubectl -n omni-compass exec deploy/omni-compass -- touch /tmp/omni.kill
```

The switch is one human-operated switch for the whole harness (OFF restores every HPA target, replica range, CPU
limit and cordon Omni-Compass changed, and records it; removing the file turns Omni-Compass back ON). It never fires by
itself and never switches off one module: a failed decision is skipped, boundaries are held by the living band.

## 0. Build the image
```
docker build -f deploy/Dockerfile -t <registry>/omni-compass:<tag> .
docker push <registry>/omni-compass:<tag>
```
**What the image contains.**
- The engine.
- The nervous system.
- The live controller and its levers.
- The frozen closure-law setting (`/app/law/closure.json`).

**How it runs.** As a non-root user, with a read-only root filesystem and no Linux capabilities.

## 1. Shadow: read-only, decides and logs, never writes
```
kubectl apply -f deploy/install/omni-compass.yaml      # set the image line first
kubectl -n omni-compass logs deploy/omni-compass -f
```
**Proof of read-only.** `scripts/pilot_shadow.sh` runs the same stage from a workstation with `kubectl auth can-i`
receipts that the identity cannot write, and writes `SHADOW_REPORT.md`.

**Run length.** One to two weeks.

**Pass condition.** Zero writes, and recommendations you agree with.

## 2. Target: Omni-Compass sets each HPA's CPU target
```
kubectl apply -f deploy/rbac-target.yaml               # adds: patch horizontalpodautoscalers
kubectl -n omni-compass patch deploy omni-compass --type=json -p \
  '[{"op":"replace","path":"/spec/template/spec/containers/0/args/1","value":"target"}]'
```
**What happens.** The HPAs keep scaling pods. Omni-Compass only moves their target within bounds.

**The SLO reflex.** Add `--latency-file` and `--slo-ms`, and the target is never tighter than native while the SLO is
breached.

**Pass condition.** Latency no worse than native, and fewer pod-hours.

## 3. Node pool: Omni-Compass sizes the node pool
**Add permissions.** `patch nodes`, `create pods/eviction` (`deploy/kind/rbac-omni.yaml` is the tested example).

**Set the mode.** `--mode nodepool --node-scale-cmd "<your pool resize command with {n}>"`. Examples of the resize
command:
- a Karpenter NodePool limit;
- a cloud node-group size;
- `scripts/kind_nodepool.sh` on kind.

**What guards a release.** The machine organ gives a node back only when all of these hold:
- every sense is live;
- its last order landed;
- pods are not scaling up;
- nothing is pending;
- the remaining nodes stay at or below the engine's target utilisation.

A PodDisruptionBudget on each service is required, because drains go through the eviction API.

**Optional levers.** Each has its own flag and permissions, and all are listed in `omni_controller/muscles.py`:
- right-sizing;
- cold start;
- batch pacing;
- agent containment;
- cooling;
- CPU frequency.

## Evidence, and where it is
| Evidence | File |
|---|---|
| The controller, every lever and the Unified Control Switch on real Kubernetes (kind) | `results/live/LIVE_LEVERS_2_NERVOUS.txt` |
| Read-only shadow on real Kubernetes: every decision logged, 0 writes | `results/live/LIVE_SHADOW_1.txt` |
| Least-privilege identity receipts | `rbac_omni.txt` in every live run |
| Native vs Omni on top vs Omni alone, paired on one machine, real Kubernetes | `results/live/LIVE_PAIRED.md` |
| The full wiring manual | `docs/OPERATOR_MANUAL.md` |
