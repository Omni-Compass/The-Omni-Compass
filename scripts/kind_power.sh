#!/usr/bin/env bash
# Declared power model for a kind cluster (kind nodes have no power meter): prints site watts as
#   sum over schedulable workers of IDLE_W + DYN_W * CPU utilisation of that worker
#   + STANDBY_W for every parked (cordoned) worker.
# STANDBY_W defaults to IDLE_W: a parked worker stays powered and ready (standby), so parking alone saves nothing.
# Set STANDBY_W lower only for a declared low-power state (sleep) or 0 for machines that are really powered off.
set -euo pipefail
KUBECTL="${KUBECTL:-kubectl}"   # kind_bench.sh sets this to scripts/kubectl_omni.sh (least privilege)
IDLE_W="${IDLE_W:-100}"; DYN_W="${DYN_W:-150}"; STANDBY_W="${STANDBY_W:-$IDLE_W}"
nodes=$($KUBECTL get nodes -l '!node-role.kubernetes.io/control-plane' -o json)
parked=$(echo "$nodes" | jq '[.items[] | select(.spec.unschedulable == true)] | length')
mapfile -t active < <(echo "$nodes" | jq -r '.items[]
  | select(.spec.unschedulable != true)
  | select(any(.status.conditions[]; .type=="Ready" and .status=="True"))
  | .metadata.name')
$KUBECTL top nodes --no-headers 2>/dev/null | awk -v idle="$IDLE_W" -v dyn="$DYN_W" -v sb="$STANDBY_W" -v parked="$parked" -v names="${active[*]}" '
  BEGIN { n = split(names, a, " "); for (i = 1; i <= n; i++) on[a[i]] = 1 }
  ($1 in on) { u = $3; sub(/%$/, "", u); u = u + 0; if (u > 100) u = 100; w += idle + dyn * u / 100; seen[$1] = 1 }
  END { for (k in on) if (!(k in seen)) w += idle; w += parked * sb; printf "%.1f\n", w }'
