#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# Omni-Compass on a real Kubernetes control plane at scale: a kind cluster whose worker nodes are KWOK nodes (the
# Kubernetes project's own tool: real Node and Pod objects in the real API server, no machines behind them).
#
#   NODES=500 bash scripts/kwok_scale.sh
#
# It builds NODES worker nodes (4 CPU each), NODES/10 Deployments with their HPAs (CPU target 50) and two pods per node,
# then runs the controller (bowl law, HPA target and node pool, the verdict) for ITER decisions against a response-time
# feed that is calm, then hot, then calm. It measures what the controller costs at that size (decision time, its own
# CPU) and checks that its counts are right and its commands land; then the master switch turns the whole harness off,
# and every HPA target and every node must be back as the operator had them. Writes $OUT/KWOK.json.
set -euo pipefail
cd "$(dirname "$0")/.."
NODES="${NODES:-50}"; ITER="${ITER:-12}"; INTERVAL="${INTERVAL:-10}"; OUT="${OUT:-kwok-$NODES}"
KWOK_VERSION="${KWOK_VERSION:-v0.6.1}"
mkdir -p "$OUT"
kind create cluster --name omni-kwok --wait 120s >/dev/null
kubectl apply -f "https://github.com/kubernetes-sigs/kwok/releases/download/$KWOK_VERSION/kwok.yaml" >/dev/null
kubectl apply -f "https://github.com/kubernetes-sigs/kwok/releases/download/$KWOK_VERSION/stage-fast.yaml" >/dev/null
kubectl -n kube-system rollout status deployment/kwok-controller --timeout=180s >/dev/null
python3 - "$NODES" > "$OUT/objects.yaml" <<'PY'
import sys
n = int(sys.argv[1])
for i in range(n):
    print(f"""---
apiVersion: v1
kind: Node
metadata:
  name: kwok-{i}
  annotations: {{node.alpha.kubernetes.io/ttl: "0", kwok.x-k8s.io/node: fake}}
  labels: {{type: kwok, kubernetes.io/role: agent}}
spec:
  taints: [{{key: kwok.x-k8s.io/node, value: fake, effect: NoSchedule}}]
status:
  allocatable: {{cpu: "4", memory: 16Gi, pods: "110"}}
  capacity: {{cpu: "4", memory: 16Gi, pods: "110"}}""")
for d in range(max(1, n // 10)):
    print(f"""---
apiVersion: apps/v1
kind: Deployment
metadata: {{name: web-{d}, namespace: default}}
spec:
  replicas: 20
  selector: {{matchLabels: {{app: web-{d}}}}}
  template:
    metadata: {{labels: {{app: web-{d}}}}}
    spec:
      nodeSelector: {{type: kwok}}
      tolerations: [{{key: kwok.x-k8s.io/node, operator: Exists, effect: NoSchedule}}]
      containers: [{{name: app, image: fake, resources: {{requests: {{cpu: 500m}}, limits: {{cpu: 500m}}}}}}]
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {{name: web-{d}, namespace: default}}
spec:
  scaleTargetRef: {{apiVersion: apps/v1, kind: Deployment, name: web-{d}}}
  minReplicas: 1
  maxReplicas: 40
  metrics: [{{type: Resource, resource: {{name: cpu, target: {{type: Utilization, averageUtilization: 50}}}}}}]""")
PY
t0=$(date +%s.%N)
kubectl apply -f "$OUT/objects.yaml" --server-side >/dev/null
kubectl wait --for=condition=Ready node -l type=kwok --timeout=600s >/dev/null
t1=$(date +%s.%N)
ready=$(kubectl get nodes -l type=kwok --no-headers | grep -c ' Ready' || true)
echo "nodes ready: $ready of $NODES ($(python3 -c "print(round($t1-$t0,1))") s)"
# the response-time feed: calm, then hot (past the SLO), then calm again
python3 - "$OUT/latency.csv" "$(( ITER * INTERVAL ))" <<'PY' &
import sys, time
path, dur = sys.argv[1], float(sys.argv[2])
t0 = time.time()
with open(path, "w") as f:
    f.write("elapsed_seconds,latency_ms,ok\n"); f.flush()
    while time.time() - t0 < dur + 30:
        e = time.time() - t0
        ms = 900.0 if dur * 0.35 < e < dur * 0.55 else 80.0
        f.write(f"{e:.2f},{ms},1\n"); f.flush(); time.sleep(0.5)
PY
feed=$!
export OMNI_MASTER_OFF="$PWD/$OUT/switch/OFF"
set +e
/usr/bin/time -v python3 -m omni_controller.controller --kubectl deploy/kwok/kubectl_kwok.sh --mode nodepool --active-nodes-only --law bowl --interval "$INTERVAL" \
  --iterations "$ITER" --min-nodes 1 --max-nodes "$NODES" --max-node-step 1 \
  --node-scale-cmd "bash scripts/kind_nodepool.sh {n}" --node-restore-cmd "bash scripts/kind_nodepool.sh $NODES" \
  --latency-file "$OUT/latency.csv" --slo-ms 500 --latency-window-s 20 --audit "$OUT/audit.jsonl" --kill-file "$OUT/kill" \
  > "$OUT/controller.log" 2> "$OUT/time.txt" &
omni=$!
sleep $(( ITER * INTERVAL * 3 / 4 ))
python3 tools/omni_switch.py off --reason "scale test" --wait 300 > "$OUT/switch.txt" 2>&1
switch_rc=$?
wait "$omni"; kill "$feed" 2>/dev/null
set -e
targets=$(kubectl get hpa -A -o jsonpath='{range .items[*]}{.spec.metrics[0].resource.target.averageUtilization}{"\n"}{end}' | sort | uniq -c | tr '\n' ';')
closed=$(kubectl get nodes -l type=kwok -o json | jq '[.items[] | select(.spec.unschedulable == true or any(.spec.taints[]?; .key == "omnicompass.io/idle"))] | length')
python3 - "$OUT" "$NODES" "$ready" "$switch_rc" "$targets" "$closed" <<'PY'
import json, re, sys
out, n, ready, rc, targets, closed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6])
rows = [json.loads(l) for l in open(f"{out}/audit.jsonl")]
dms = [r["decision_ms"] for r in rows if "decision_ms" in r]
ov = [r["overhead"] for r in rows if "overhead" in r]
dec = [r["decision"] for r in rows if isinstance(r.get("decision"), dict)]
obs = [d.get("nodes_observed") for d in dec]
tv = open(f"{out}/time.txt").read()
rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", tv)
res = {"nodes": n, "nodes_ready": ready, "decisions": len(dms),
       "decision_ms": {"median": sorted(dms)[len(dms) // 2] if dms else None, "max": max(dms) if dms else None},
       "controller_cpu_s": ov[-1]["cpu_s"] if ov else None, "controller_wall_s": ov[-1]["wall_s"] if ov else None,
       "controller_cores_mean": ov[-1]["cores_mean"] if ov else None,
       "controller_max_rss_mb": round(int(rss.group(1)) / 1024, 1) if rss else None,
       "nodes_observed": obs, "node_commands": sum(1 for r in rows if "node_command" in json.dumps(r)),
       "verdict_events": [r["verdict"] for r in rows if "verdict" in r and isinstance(r["verdict"], dict)],
       "master_switch_rc": rc, "hpa_targets_after": targets, "nodes_closed_after": closed,
       "handed_back": rc == 0 and closed == 0 and targets.strip(" ;").split()[-1] == "50" and len(targets.strip(";").split(";")) == 1}
json.dump(res, open(f"{out}/KWOK.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("nodes_observed", "verdict_events")}))
PY
kind delete cluster --name omni-kwok >/dev/null 2>&1 || true
