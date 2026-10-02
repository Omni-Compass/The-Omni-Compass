#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# One command: the whole live comparison on real Kubernetes (kind) on any machine with Docker.
# For each repetition it builds a fresh 7-node cluster (1 control plane + 6 workers) and runs three arms in turn:
#   native  Kubernetes alone (HPA, scheduler)
#   omni    Omni-Compass on top (B): closure law, nervous system, levers, kill switch at the end
#   strict  Omni-Compass decides replicas and nodes (C)
# then aggregates every repetition into live_runs/LIVE_REPS.md (paired differences, 95% intervals).
# Needs: docker, kind (v0.27+), kubectl, python3 with requirements.txt, jq, curl. About 20 minutes per arm.
# Usage:  bash RUN_LIVE.sh [repetitions=3] [seconds_per_arm=900]
set -euo pipefail
REPS="${1:-3}"; DUR="${2:-900}"; OUT=live_runs
for t in docker kind kubectl jq curl python3; do command -v "$t" >/dev/null || { echo "missing: $t"; exit 1; }; done
pip install -q -r requirements.txt
mkdir -p "$OUT"
for rep in $(seq 1 "$REPS"); do
  for arm in native omni strict; do
    echo "=== repetition $rep, arm $arm ==="
    kind delete cluster --name omni-bench >/dev/null 2>&1 || true
    kind create cluster --name omni-bench --config deploy/kind/cluster-full.yaml --wait 300s
    ARM="$arm" OUT_DIR="$OUT/bench-$arm-$rep" DURATION="$DUR" CLOSURE=tuning/GLOBAL_LEAGUE_PREREGISTRATION.json \
      bash scripts/kind_bench.sh || echo "arm $arm repetition $rep FAILED (kept in $OUT/bench-$arm-$rep)"
  done
done
kind delete cluster --name omni-bench >/dev/null 2>&1 || true
python3 tools/live_reps.py "$OUT"
echo; echo "Results: $OUT/LIVE_REPS.md  (every run's audit, decision trail and capture are in $OUT/bench-*)"
