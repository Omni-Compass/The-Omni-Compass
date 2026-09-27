# Wiring Omni-Compass into your Kubernetes

**Three stages.** Each stage adds only the permissions it needs. A stage is promoted only after its evidence is in,
and the kill switch works at every stage:

```
kubectl -n omni-compass exec deploy/omni-compass -- touch /tmp/omni.kill
```

The kill switch restores every HPA target, replica range, CPU limit and cordon that Omni-Compass changed, and records
the restore in its audit.

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

## What is proven, and where
| Evidence | File |
|---|---|
| The controller, every lever and the kill switch on real Kubernetes (kind): 19 of 19 checks, run twice | `results/live/LIVE_LEVERS_1.txt`, `LIVE_LEVERS_2_NERVOUS.txt` |
| Read-only shadow on real Kubernetes: 40 decisions, 0 writes | `results/live/LIVE_SHADOW_1.txt` |
| Least-privilege identity receipts | `results/live/LIVE_RBAC_1.json`, `rbac_omni.txt` in each run |
| The paired live comparison with a working probe: equal to native on every gauge; Omni-Compass held all 6 machines | `results/live/LIVE_REPS_3.md` |
| Why it held them, and the fix (release gate, two-way nervous system) | `results/live/LIVE_REPS_4_DIAGNOSIS.md`, `docs/TWO_WAY_NERVOUS_SYSTEM.md` |
| Each gate reason, shown on the stand-in cluster | `results/local_run/NERVOUS_SYSTEM_DEMO.txt` |

**Not yet proven live.** Machine savings with the new release gate. `bash RUN_LIVE.sh 3` measures them on your own
machine.
