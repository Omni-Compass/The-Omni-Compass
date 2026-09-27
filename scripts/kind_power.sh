#!/usr/bin/env bash
# Declared power model for a kind cluster (kind nodes have no power meter): prints site watts as
#   sum over schedulable workers of IDLE_W + DYN_W * CPU utilisation of that worker
#   + STANDBY_W for every parked (cordoned) worker.
# An idling worker stays powered and Ready at STANDBY_W (declared by the caller; kind_bench.sh sets park_frac x idle).
set -euo pipefail
KUBECTL="${KUBECTL:-kubectl}"   # kind_bench.sh sets this to scripts/kubectl_omni.sh (least privilege)
IDLE_W="${IDLE_W:-100}"; DYN_W="${DYN_W:-150}"; STANDBY_W="${STANDBY_W:-$IDLE_W}"
nodes=$($KUBECTL get nodes -l '!node-role.kubernetes.io/control-plane' -o json)
# a worker carrying work (any running or starting pod that is not a DaemonSet's) is in service even while cordoned;
# only a cordoned worker with no work left idles at STANDBY_W
carrying=$($KUBECTL get pods -A -o json | jq -r '[.items[] | select(.status.phase=="Running" or .status.phase=="Pending")
  | select(all(.metadata.ownerReferences[]?; .kind != "DaemonSet")) | .spec.nodeName // empty] | unique | join(" ")')
parked=$(echo "$nodes" | jq --arg c " $carrying " '[.items[] | select(.spec.unschedulable == true)
  | select(.metadata.name as $n | ($c | contains(" " + $n + " ")) | not)] | length')
mapfile -t active < <(echo "$nodes" | jq -r --arg c " $carrying " '.items[]
  | select(.metadata.name as $n | .spec.unschedulable != true or ($c | contains(" " + $n + " ")))
  | select(any(.status.conditions[]; .type=="Ready" and .status=="True"))
  | .metadata.name')
$KUBECTL top nodes --no-headers 2>/dev/null | awk -v idle="$IDLE_W" -v dyn="$DYN_W" -v sb="$STANDBY_W" -v parked="$parked" -v names="${active[*]}" '
  BEGIN { n = split(names, a, " "); for (i = 1; i <= n; i++) on[a[i]] = 1 }
  ($1 in on) { u = $3; sub(/%$/, "", u); u = u + 0; if (u > 100) u = 100; w += idle + dyn * u / 100; seen[$1] = 1 }
  END { for (k in on) if (!(k in seen)) w += idle; w += parked * sb; printf "%.1f\n", w }'
