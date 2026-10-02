#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# Live pilot on a real Kubernetes control plane (kind): real scheduler, real HPA, real metrics-server.
# Phase A: baseline (HPA alone; Omni in observe mode, writing nothing). Phase B: Omni in target mode.
# Then the kill switch is exercised and the original HPA target must be restored. Results in $OUT_DIR.
set -euo pipefail
OUT_DIR="${OUT_DIR:-kind_pilot_out}"; PHASE_S="${PHASE_S:-600}"; mkdir -p "$OUT_DIR"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deployment/metrics-server --timeout=300s
kubectl apply -f deploy/kind/demo.yaml
kubectl rollout status deployment/php-apache --timeout=300s
kubectl run load-generator --image=busybox:1.36 --restart=Never -- /bin/sh -c \
  "while true; do for i in \$(seq 1 20); do wget -q -O- http://php-apache >/dev/null; done; sleep \$((RANDOM % 3)); done"
for i in $(seq 1 30); do kubectl top nodes >/dev/null 2>&1 && break; sleep 10; done

echo "== Phase A: baseline (HPA alone, Omni observing)"
python -m omni_controller.controller --mode observe --interval 60 --iterations $((PHASE_S / 60)) \
  --audit "$OUT_DIR/audit_observe.jsonl" --kill-file "$OUT_DIR/kill" &
OUT="$OUT_DIR/baseline.csv" INTERVAL=15 DURATION="$PHASE_S" bash fleet/capture/kube_capture.sh
wait

echo "== Phase B: Omni target mode (writes the HPA target)"
python -m omni_controller.controller --mode target --interval 60 --iterations $((PHASE_S / 60)) \
  --audit "$OUT_DIR/audit_target.jsonl" --kill-file "$OUT_DIR/kill" &
OUT="$OUT_DIR/omni.csv" INTERVAL=15 DURATION="$PHASE_S" bash fleet/capture/kube_capture.sh
wait
kubectl get hpa php-apache -o json > "$OUT_DIR/hpa_after_target.json"

echo "== Kill switch: the original target (50) must be restored"
touch "$OUT_DIR/kill"
python -m omni_controller.controller --mode target --iterations 1 --audit "$OUT_DIR/audit_kill.jsonl" --kill-file "$OUT_DIR/kill"
restored=$(kubectl get hpa php-apache -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}')
echo "restored target: $restored" | tee "$OUT_DIR/kill_switch.txt"
test "$restored" = "50"

python pilot/score.py --baseline "$OUT_DIR/baseline.csv" --omni "$OUT_DIR/omni.csv" --idle-w 100 --dyn-w 150 \
  --block-minutes 2 --out "$OUT_DIR/SCORE.json" | tee "$OUT_DIR/score.txt"
echo "writes during observe phase: $(grep -c '"write"' "$OUT_DIR/audit_observe.jsonl" || true)" | tee "$OUT_DIR/observe_writes.txt"
