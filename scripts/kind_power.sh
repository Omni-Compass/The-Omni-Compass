#!/usr/bin/env bash
# Declared power model for a kind cluster (kind nodes have no power meter): prints site watts as
#   sum over schedulable workers of IDLE_W + DYN_W * CPU utilisation of that worker.
# The same model and constants are passed to pilot/score.py, so the power the governor senses and the energy the
# score reports agree. Parked (cordoned) workers draw nothing in this model.
set -euo pipefail
IDLE_W="${IDLE_W:-100}"; DYN_W="${DYN_W:-150}"
nodes=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o json)
mapfile -t active < <(echo "$nodes" | jq -r '.items[]
  | select(.spec.unschedulable != true)
  | select(any(.status.conditions[]; .type=="Ready" and .status=="True"))
  | .metadata.name')
kubectl top nodes --no-headers 2>/dev/null | awk -v idle="$IDLE_W" -v dyn="$DYN_W" -v names="${active[*]}" '
  BEGIN { n = split(names, a, " "); for (i = 1; i <= n; i++) on[a[i]] = 1 }
  ($1 in on) { u = $3; sub(/%$/, "", u); u = u + 0; if (u > 100) u = 100; w += idle + dyn * u / 100; seen[$1] = 1 }
  END { for (k in on) if (!(k in seen)) w += idle; printf "%.1f\n", w }'
