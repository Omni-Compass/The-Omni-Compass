#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# Full-engine live pilot on a multi-node kind cluster (deploy/kind/cluster-full.yaml): real API server, scheduler,
# HPA and metrics-server, six workers forming the node pool.
#   Phase A  baseline: HPA alone on all workers; Omni-Compass observing (must write nothing).
#   Phase B  full engine: Omni-Compass drives the wired muscles live -
#              hpa        HPA CPU target (rho*)
#              nodes      node-pool size: cordon + drain specific workers, uncordon for pending pods
#              power_cap  senses site power (declared model, scripts/kind_power.sh) into the governor
#   Kill     the kill switch must restore the HPA target (50) and return every worker to service.
# Results in $OUT_DIR.
set -euo pipefail
OUT_DIR="${OUT_DIR:-kind_full_out}"; PHASE_S="${PHASE_S:-600}"; mkdir -p "$OUT_DIR"
IDLE_W="${IDLE_W:-100}"; DYN_W="${DYN_W:-150}"; export IDLE_W DYN_W
WORKERS=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' --no-headers | wc -l)
SITE_LIMIT_W=$(( WORKERS * (IDLE_W + DYN_W) ))

kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
# Keep cluster add-ons on the control plane so parking a worker never interrupts metrics or DNS.
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
kubectl get nodes -o wide | tee "$OUT_DIR/nodes_start.txt"

CAPTURE="ACTIVE_ONLY=1 INTERVAL=15 DURATION=$PHASE_S"

echo "== Phase A: baseline (HPA alone on $WORKERS workers, Omni observing)"
python -m omni_controller.controller --mode observe --active-nodes-only --interval 60 --iterations $((PHASE_S / 60)) \
  --power-cmd "bash scripts/kind_power.sh" --site-limit-w "$SITE_LIMIT_W" \
  --audit "$OUT_DIR/audit_observe.jsonl" --kill-file "$OUT_DIR/kill" &
env $CAPTURE OUT="$OUT_DIR/baseline.csv" bash fleet/capture/kube_capture.sh
wait

echo "== Phase B: full engine (HPA target + node pool + power sensing)"
python -m omni_controller.controller --mode nodepool --active-nodes-only --interval 60 --floor-interval 15 \
  --iterations $((PHASE_S / 60)) --min-nodes 1 --max-nodes "$WORKERS" --max-node-step 1 \
  --node-scale-cmd "bash scripts/kind_nodepool.sh {n}" --node-restore-cmd "bash scripts/kind_nodepool.sh $WORKERS" \
  --power-cmd "bash scripts/kind_power.sh" --site-limit-w "$SITE_LIMIT_W" \
  --audit "$OUT_DIR/audit_full.jsonl" --kill-file "$OUT_DIR/kill" &
env $CAPTURE OUT="$OUT_DIR/omni.csv" bash fleet/capture/kube_capture.sh
wait
kubectl get hpa php-apache -o json > "$OUT_DIR/hpa_after_full.json"
kubectl get nodes -o wide | tee "$OUT_DIR/nodes_after_full.txt"

echo "== Kill switch: HPA target 50 and all $WORKERS workers must be restored"
touch "$OUT_DIR/kill"
python -m omni_controller.controller --mode nodepool --active-nodes-only --iterations 1 \
  --node-restore-cmd "bash scripts/kind_nodepool.sh $WORKERS" \
  --audit "$OUT_DIR/audit_kill.jsonl" --kill-file "$OUT_DIR/kill"
restored=$(kubectl get hpa php-apache -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}')
back=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o json | jq '[.items[] | select(.spec.unschedulable != true)] | length')
{ echo "restored target: $restored"; echo "workers in service: $back of $WORKERS"; } | tee "$OUT_DIR/kill_switch.txt"

python pilot/score.py --baseline "$OUT_DIR/baseline.csv" --omni "$OUT_DIR/omni.csv" --idle-w "$IDLE_W" --dyn-w "$DYN_W" \
  --block-minutes 2 --out "$OUT_DIR/SCORE.json" | tee "$OUT_DIR/score.txt"
echo "writes during observe phase: $(grep -c '"write"' "$OUT_DIR/audit_observe.jsonl" || true)" | tee "$OUT_DIR/observe_writes.txt"
{
  echo "muscle actions during the full-engine phase:"
  echo "  hpa target writes:   $(grep -c 'HPA target to rho' "$OUT_DIR/audit_full.jsonl" || true)"
  echo "  node pool resizes:   $(grep -c '"why": "node pool size"' "$OUT_DIR/audit_full.jsonl" || true)"
  echo "  scheduling-floor adds: $(grep -c 'scheduling floor' "$OUT_DIR/audit_full.jsonl" || true)"
  echo "  node counts decided: $(jq -r 'select(.decision.nodes_recommended) | .decision.nodes_recommended' "$OUT_DIR/audit_full.jsonl" | tr '\n' ' ')"
} | tee "$OUT_DIR/muscles.txt"
test "$restored" = "50"
test "$back" = "$WORKERS"
