#!/usr/bin/env bash
# Paired live repetition: every arm runs back to back on the SAME runner (same CPUs, same host, same noise), each on a
# fresh kind cluster, in an order rotated by repetition so no arm always runs first or last. Differences between arms in
# one repetition are then differences between arms, not between machines (separate runners differ by about 15% in
# p95 on their own).
# Usage: REP=n ARMS="native omni" bash scripts/kind_paired.sh   (Omni governs the muscles it is given: native vs Omni on top)
set -euo pipefail
REP="${REP:?set REP}"; read -r -a arms <<< "${ARMS:-native omni}"
k=${#arms[@]}; off=$(( (REP - 1) % k ))
order=( "${arms[@]:off}" "${arms[@]:0:off}" )
echo "repetition $REP, order: ${order[*]}"
for arm in "${order[@]}"; do
  kind delete cluster --name omni-bench >/dev/null 2>&1 || true
  kind create cluster --name omni-bench --config deploy/kind/cluster-full.yaml --wait 120s
  echo "######## ARM $arm (repetition $REP)"
  if ! ARM="$arm" OUT_DIR="bench-$arm-$REP" bash scripts/kind_bench.sh; then
    # a run that fails its own checks is recorded as invalid and left out of the table, never silently counted
    echo "ARM $arm (repetition $REP) FAILED its checks: marked invalid" | tee "bench-$arm-$REP/INVALID"; fail=1
  fi
done
kind delete cluster --name omni-bench >/dev/null 2>&1 || true
exit "${fail:-0}"
