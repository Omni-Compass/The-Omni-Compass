#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# The fault test (FAULTS=1 in scripts/kind_bench.sh): the same four faults at the same moments of every arm, so native
# Kubernetes alone and Kubernetes with Omni-Compass on top meet exactly the same trouble. Times are shares of DURATION.
#   machine   at 15%: a worker machine dies (its kind container is stopped); it comes back two minutes later
#   spike     at 35%: traffic triples for two minutes (a second open-rate load generator, RATE 12, on the control plane)
#   runaway   at 55%: a pod with no CPU limit burns CPU on a worker for two minutes
#   blind     at 75%: the response-time probe stops reporting for one minute (paused, then resumed)
# Every fault and its recovery is written to $OUT_DIR/faults.log with its time.
# Usage: OUT_DIR=... DURATION=... PROBE_PID=... bash scripts/kind_faults.sh
set -u
D="${DURATION:?}"; LOG="${OUT_DIR:?}/faults.log"; CLUSTER="${KIND_CLUSTER:-omni-bench}"
say() { echo "$(date -u +%s) $*" | tee -a "$LOG"; }
at() { sleep "$(( D * $1 / 100 ))"; }
t0=$(date +%s)
wait_until() { local s=$(( t0 + D * $1 / 100 )); local now; now=$(date +%s); (( s > now )) && sleep $(( s - now )); }
wait_until 15
victim=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o jsonpath='{.items[-1].metadata.name}')
say "machine down: $victim"; docker stop "$victim" >/dev/null 2>&1 || say "machine down failed"
sleep 120; docker start "$victim" >/dev/null 2>&1; say "machine back: $victim"
wait_until 35
say "spike: traffic x3"
kubectl get deployment load-generator -o json | jq '.metadata.name="load-spike" | .spec.selector.matchLabels.app="load-spike"
  | .spec.template.metadata.labels.app="load-spike" | .spec.template.spec.containers[0].env=[{"name":"RATE","value":"12"}]
  | del(.metadata.uid,.metadata.resourceVersion,.metadata.creationTimestamp,.metadata.annotations,.metadata.generation,.status)' \
  | kubectl apply -f - >/dev/null
sleep 120; kubectl delete deployment load-spike --wait=false >/dev/null 2>&1; say "spike over"
wait_until 55
say "runaway pod started"
kubectl run runaway --image=busybox:1.36 --restart=Never --overrides='{"spec":{"nodeSelector":{"kubernetes.io/os":"linux"}}}' \
  -- /bin/sh -c 'while :; do :; done' >/dev/null 2>&1
sleep 120; kubectl delete pod runaway --grace-period=0 --force >/dev/null 2>&1; say "runaway pod removed"
wait_until 75
if [ -n "${PROBE_PID:-}" ]; then
  say "probe blind"; kill -STOP "$PROBE_PID" 2>/dev/null; sleep 60; kill -CONT "$PROBE_PID" 2>/dev/null; say "probe back"
fi
