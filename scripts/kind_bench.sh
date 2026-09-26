#!/usr/bin/env bash
# One arm of the native-vs-Omni benchmark on the six-worker kind cluster (deploy/kind/cluster-full.yaml).
# Both arms are wired identically: same cluster, add-ons, workload, HPA (target 50), load schedule, capture and
# power model. The only difference:
#   ARM=native  Omni-Compass is not started at all. Kubernetes (HPA, scheduler) runs alone on all workers.
#   ARM=omni    Omni-Compass runs in nodepool mode: HPA target, node pool (cordon/drain/uncordon), power sensing.
# Load schedule: the load-generator replica count steps through LOAD_STEPS, each step DURATION/steps seconds,
# identical in both arms. Results in $OUT_DIR: capture.csv (every 15 s), nodes timeline, Omni audit (omni arm).
set -euo pipefail
ARM="${ARM:?set ARM=native or ARM=omni}"
OUT_DIR="${OUT_DIR:-bench_$ARM}"; DURATION="${DURATION:-1200}"; WARMUP="${WARMUP:-120}"
LOAD_STEPS="${LOAD_STEPS:-1 2 3 1 2 1}"
IDLE_W="${IDLE_W:-100}"; DYN_W="${DYN_W:-150}"; export IDLE_W DYN_W
mkdir -p "$OUT_DIR"
WORKERS=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' --no-headers | wc -l)
SITE_LIMIT_W=$(( WORKERS * (IDLE_W + DYN_W) ))

kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
pin='{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":""},"tolerations":[{"key":"node-role.kubernetes.io/control-plane","operator":"Exists","effect":"NoSchedule"}]}}}}'
kubectl -n kube-system patch deployment metrics-server -p "$pin"
kubectl -n kube-system patch deployment coredns -p "$pin"
kubectl -n kube-system rollout status deployment/metrics-server --timeout=300s
kubectl -n kube-system rollout status deployment/coredns --timeout=300s
kubectl apply -f deploy/kind/demo.yaml
kubectl rollout status deployment/php-apache --timeout=300s
kubectl apply -f deploy/kind/loadgen.yaml
kubectl rollout status deployment/load-generator --timeout=300s
for i in $(seq 1 30); do kubectl top nodes >/dev/null 2>&1 && break; sleep 10; done
echo "== warm-up ${WARMUP}s (both arms)"; sleep "$WARMUP"

read -r -a steps <<< "$LOAD_STEPS"
step_s=$(( DURATION / ${#steps[@]} ))
( for r in "${steps[@]}"; do
    echo "$(date -u +%H:%M:%S) load-generator replicas -> $r"
    kubectl scale deployment/load-generator --replicas="$r" >/dev/null
    sleep "$step_s"
  done ) > "$OUT_DIR/load_schedule.log" 2>&1 &
load_pid=$!

omni_pid=""
if [ "$ARM" = "omni" ]; then
  echo "== ARM omni: Omni-Compass driving HPA target + node pool + power sensing"
  python -m omni_controller.controller --mode nodepool --active-nodes-only --interval 60 --floor-interval 15 \
    --iterations $(( DURATION / 60 )) --min-nodes 1 --max-nodes "$WORKERS" --max-node-step 1 \
    --node-scale-cmd "bash scripts/kind_nodepool.sh {n}" --node-restore-cmd "bash scripts/kind_nodepool.sh $WORKERS" \
    --power-cmd "bash scripts/kind_power.sh" --site-limit-w "$SITE_LIMIT_W" \
    --audit "$OUT_DIR/audit.jsonl" --kill-file "$OUT_DIR/kill" > "$OUT_DIR/controller.log" 2>&1 &
  omni_pid=$!
else
  echo "== ARM native: Omni-Compass not running; Kubernetes alone"
fi

ACTIVE_ONLY=1 INTERVAL=15 DURATION="$DURATION" POWER_CMD="bash scripts/kind_power.sh" OUT="$OUT_DIR/capture.csv" \
  bash fleet/capture/kube_capture.sh
wait "$load_pid" || true
[ -n "$omni_pid" ] && { wait "$omni_pid" || true; }
kubectl get nodes -o wide > "$OUT_DIR/nodes_end.txt"
kubectl get hpa php-apache -o json > "$OUT_DIR/hpa_end.json"

if [ "$ARM" = "omni" ]; then
  echo "== kill switch"
  touch "$OUT_DIR/kill"
  python -m omni_controller.controller --mode nodepool --active-nodes-only --iterations 1 \
    --node-restore-cmd "bash scripts/kind_nodepool.sh $WORKERS" --audit "$OUT_DIR/audit_kill.jsonl" --kill-file "$OUT_DIR/kill"
  restored=$(kubectl get hpa php-apache -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}')
  back=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o json | jq '[.items[] | select(.spec.unschedulable != true)] | length')
  { echo "restored target: $restored"; echo "workers in service: $back of $WORKERS"; } | tee "$OUT_DIR/kill_switch.txt"
  test "$restored" = "50" && test "$back" = "$WORKERS"
fi
echo "rows captured: $(( $(wc -l < "$OUT_DIR/capture.csv") - 1 ))"
