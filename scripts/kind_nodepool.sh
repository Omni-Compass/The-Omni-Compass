#!/usr/bin/env bash
# Node-pool actuator for a kind cluster: keep exactly N worker nodes schedulable.
# Scale-down cordons and drains specific workers (fewest non-DaemonSet pods first) so their pods are rescheduled;
# scale-up uncordons parked workers. A parked kind node is still a running container: it is counted as off because it
# carries no workload, as a removed node in a cloud node pool would. Usage: bash scripts/kind_nodepool.sh N
set -euo pipefail
want="${1:?usage: kind_nodepool.sh N}"
workers=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o json)
mapfile -t active < <(echo "$workers" | jq -r '.items[] | select(.spec.unschedulable != true) | .metadata.name')
mapfile -t parked < <(echo "$workers" | jq -r '.items[] | select(.spec.unschedulable == true) | .metadata.name')
total=$(( ${#active[@]} + ${#parked[@]} ))
(( want < 1 )) && want=1
(( want > total )) && want=$total
n=${#active[@]}

if (( want > n )); then
  for node in "${parked[@]:0:$((want - n))}"; do
    kubectl uncordon "$node"
  done
elif (( want < n )); then
  mapfile -t order < <(for node in "${active[@]}"; do
      c=$(kubectl get pods -A --field-selector "spec.nodeName=$node" -o json \
          | jq '[.items[] | select(all(.metadata.ownerReferences[]?; .kind != "DaemonSet"))] | length')
      echo "$c $node"
    done | sort -n | head -n $((n - want)) | awk '{print $2}')
  for node in "${order[@]}"; do
    kubectl cordon "$node"
    if ! kubectl drain "$node" --ignore-daemonsets --delete-emptydir-data --timeout=120s; then
      echo "drain of $node failed; returning it to service" >&2
      kubectl uncordon "$node"
    fi
  done
fi
echo "schedulable workers: $(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o json | jq '[.items[] | select(.spec.unschedulable != true)] | length') (wanted $want)"
