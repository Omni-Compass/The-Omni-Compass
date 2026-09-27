#!/usr/bin/env bash
# Node-pool actuator: keep exactly N worker nodes in service; the others idle, never powered off, and no pod is ever
# moved, evicted or restarted to make that happen.
# Idle a worker: cordon it (no new work lands on it) and mark its pods first to go (controller.kubernetes.io/pod-deletion-
# cost), so the autoscaler's own scale-down removes them as the load falls. A cordoned worker still carrying work is in
# service; once its work is gone it idles, powered and Ready at its floor.
# Wake a worker: uncordon it (those still carrying work first, they are warm), clear the marks on its pods; it is in
# service at once, with no boot.
# Which workers idle: fewest serving pods first, then fewest pods, so an empty worker idles before one with work.
# Usage: bash scripts/kind_nodepool.sh N
set -euo pipefail
KUBECTL="${KUBECTL:-kubectl}"   # kind_bench.sh sets this to scripts/kubectl_omni.sh (least privilege)
want="${1:?usage: kind_nodepool.sh N}"
workers=$($KUBECTL get nodes -l '!node-role.kubernetes.io/control-plane' -o json)
mapfile -t active < <(echo "$workers" | jq -r '.items[] | select(.spec.unschedulable != true) | .metadata.name')
mapfile -t parked < <(echo "$workers" | jq -r '.items[] | select(.spec.unschedulable == true) | .metadata.name')
total=$(( ${#active[@]} + ${#parked[@]} ))
(( want < 1 )) && want=1
(( want > total )) && want=$total
n=${#active[@]}

workload_on() {   # workload pods (not DaemonSet-owned, running or starting) on node $1
  $KUBECTL get pods -A --field-selector "spec.nodeName=$1" -o json \
    | jq '[.items[] | select(.status.phase=="Running" or .status.phase=="Pending") | select(all(.metadata.ownerReferences[]?; .kind != "DaemonSet"))] | length'
}
if (( want > n )); then
  mapfile -t wake < <(for node in "${parked[@]}"; do echo "$(workload_on "$node") $node"; done | sort -rn | awk '{print $2}')
  for node in "${wake[@]:0:$((want - n))}"; do
    $KUBECTL uncordon "$node"
    for pod in $($KUBECTL get pods -A --field-selector "spec.nodeName=$node" -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}'); do
      $KUBECTL annotate -n "${pod%%/*}" "pod/${pod#*/}" controller.kubernetes.io/pod-deletion-cost- >/dev/null 2>&1 || true
    done
  done
elif (( want < n )); then
  hpas=$($KUBECTL get hpa -A -o json)
  mapfile -t served < <(echo "$hpas" | jq -r '.items[] | select(.spec.scaleTargetRef.kind == "Deployment")
      | "\(.metadata.namespace) \(.spec.scaleTargetRef.name)"' | while read -r ns dep; do
        sel=$($KUBECTL get deployment "$dep" -n "$ns" -o json | jq -r '.spec.selector.matchLabels | to_entries | map("\(.key)=\(.value)") | join(",")')
        echo "$ns $sel"
      done)
  mapfile -t order < <(for node in "${active[@]}"; do
      sv=0
      for row in "${served[@]}"; do
        read -r ns sel <<< "$row"
        sv=$(( sv + $($KUBECTL get pods -n "$ns" -l "$sel" --field-selector "spec.nodeName=$node" --no-headers 2>/dev/null | wc -l) ))
      done
      echo "$sv $(workload_on "$node") $node"
    done | sort -n -k1,1 -k2,2 | head -n $((n - want)) | awk '{print $3}')
  for node in "${order[@]}"; do
    $KUBECTL cordon "$node"
    marked=0
    for row in "${served[@]}"; do
      read -r ns sel <<< "$row"
      for pod in $($KUBECTL get pods -n "$ns" -l "$sel" --field-selector "spec.nodeName=$node" -o name); do
        $KUBECTL annotate -n "$ns" "$pod" --overwrite controller.kubernetes.io/pod-deletion-cost=-1000 >/dev/null; marked=$((marked + 1))
      done
    done
    echo "idle $node: cordoned, $marked pod(s) marked first to go; it idles when its work is gone (no pod moved)"
  done
  # one machine empties at a time: the closed machine with the least work goes first (cost -1000 x N), the next
  # after it (-1000 x (N-1)), ... so each scale-down takes whole machines' work, not one pod from each
  mapfile -t closed < <($KUBECTL get nodes -l '!node-role.kubernetes.io/control-plane' -o json \
      | jq -r '.items[] | select(.spec.unschedulable == true) | .metadata.name' | while read -r node; do
        sv=0
        for row in "${served[@]}"; do
          read -r ns sel <<< "$row"
          sv=$(( sv + $($KUBECTL get pods -n "$ns" -l "$sel" --field-selector "spec.nodeName=$node" --no-headers 2>/dev/null | wc -l) ))
        done
        (( sv > 0 )) && echo "$sv $node"
      done | sort -n | awk '{print $2}')
  rank=${#closed[@]}
  for node in "${closed[@]}"; do
    for row in "${served[@]}"; do
      read -r ns sel <<< "$row"
      for pod in $($KUBECTL get pods -n "$ns" -l "$sel" --field-selector "spec.nodeName=$node" -o name); do
        $KUBECTL annotate -n "$ns" "$pod" --overwrite controller.kubernetes.io/pod-deletion-cost=$(( -1000 * rank )) >/dev/null
      done
    done
    echo "first to go, order $(( ${#closed[@]} - rank + 1 )): $node (cost $(( -1000 * rank )))"
    rank=$(( rank - 1 ))
  done
fi
echo "schedulable workers: $($KUBECTL get nodes -l '!node-role.kubernetes.io/control-plane' -o json | jq '[.items[] | select(.spec.unschedulable != true)] | length') (wanted $want)"
