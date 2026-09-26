#!/usr/bin/env bash
# Creates a kind cluster on the host's Docker, runs the Omni-Compass live pilot on it, saves results to /results.
set -euo pipefail
CLUSTER="${CLUSTER:-omni}"
PHASE_S="${PHASE_S:-300}"
KEEP_CLUSTER="${KEEP_CLUSTER:-0}"
RUN_DIR="/results/run_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_DIR"
exec > >(tee "$RUN_DIR/run.log") 2>&1

echo "== Checking Docker"
docker info >/dev/null || { echo "Cannot reach Docker. Is Docker Desktop running?"; exit 1; }

echo "== Harness self-check (verify.py --quick)"
python verify.py --quick | tail -3

echo "== Creating Kubernetes cluster '$CLUSTER' (kind) on your Docker"
kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true
kind create cluster --name "$CLUSTER" --wait 180s

# Join the cluster's Docker network so this container can reach the API server by name.
docker network connect kind "$(hostname)" 2>/dev/null || true
mkdir -p ~/.kube
kind get kubeconfig --name "$CLUSTER" --internal > ~/.kube/config
kubectl get nodes

cleanup() {
  if [ "$KEEP_CLUSTER" = "1" ]; then
    echo "== Cluster '$CLUSTER' left running (KEEP_CLUSTER=1). Remove it with: docker rm -f $CLUSTER-control-plane"
  else
    echo "== Deleting cluster '$CLUSTER'"
    kind delete cluster --name "$CLUSTER" || true
  fi
}
trap cleanup EXIT

echo "== Running live pilot (PHASE_S=$PHASE_S per phase)"
OUT_DIR="$RUN_DIR" PHASE_S="$PHASE_S" bash scripts/kind_pilot.sh

echo
echo "================ RESULTS ================"
for f in observe_writes.txt kill_switch.txt score.txt; do
  echo "--- $f"; cat "$RUN_DIR/$f"
done
echo "All files: results/$(basename "$RUN_DIR")"
