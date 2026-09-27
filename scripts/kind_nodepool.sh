#!/usr/bin/env bash
# Node-pool actuator: keep exactly N worker nodes in service; the others are parked, never powered off.
# Park: cordon the worker (no new work lands on it), move its pods, and leave it powered and Ready at its idle floor.
# Wake: uncordon a parked worker; it is in service at once, with no boot.
# Which workers: fewest serving pods first (pods of a Deployment an HPA scales), then fewest pods, so an empty worker is
# always parked before one that serves traffic.
# Make before break, as an exact swap: for the k serving pods on the worker, the HPA's floor rises by k so k replacements
# start on the other workers; when they are ready, the worker's own pods are marked first to go
# (controller.kubernetes.io/pod-deletion-cost) and the replica count is held at its level before the swap, so exactly
# those k pods leave and none is recreated. Capacity never dips below what was serving, and a move costs exactly k pod
# starts. The HPA's range returns to the operator's afterwards (also on exit). Anything left is drained through the
# eviction API, so PodDisruptionBudgets are honoured; a drain that would take the last ready replica times out after
# DRAIN_TIMEOUT and the worker goes back into service. Usage: bash scripts/kind_nodepool.sh N
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

if (( want > n )); then
  for node in "${parked[@]:0:$((want - n))}"; do
    $KUBECTL uncordon "$node"
  done
elif (( want < n )); then
  hpas=$($KUBECTL get hpa -A -o json)
  # "namespace hpa deployment selector" for every HPA that scales a Deployment
  mapfile -t served < <(echo "$hpas" | jq -r '.items[] | select(.spec.scaleTargetRef.kind == "Deployment")
      | "\(.metadata.namespace) \(.metadata.name) \(.spec.scaleTargetRef.name)"' | while read -r ns h dep; do
        sel=$($KUBECTL get deployment "$dep" -n "$ns" -o json | jq -r '.spec.selector.matchLabels | to_entries | map("\(.key)=\(.value)") | join(",")')
        echo "$ns $h $dep $sel"
      done)
  serving_on() {   # serving pods on node $1, per HPA: "namespace hpa deployment count"
    for row in "${served[@]}"; do
      read -r ns h dep sel <<< "$row"
      k=$($KUBECTL get pods -n "$ns" -l "$sel" --field-selector "spec.nodeName=$1" --no-headers 2>/dev/null | wc -l)
      (( k > 0 )) && echo "$ns $h $dep $k"
    done
    return 0
  }
  mapfile -t order < <(for node in "${active[@]}"; do
      c=$($KUBECTL get pods -A --field-selector "spec.nodeName=$node" -o json \
          | jq '[.items[] | select(all(.metadata.ownerReferences[]?; .kind != "DaemonSet"))] | length')
      s=$(serving_on "$node" | awk '{t += $4} END {print t + 0}')
      echo "$s $c $node"
    done | sort -n -k1,1 -k2,2 | head -n $((n - want)) | awk '{print $3}')
  restore=()
  restore_min() { for r in "${restore[@]}"; do read -r ns h m mx <<< "$r"; $KUBECTL patch hpa "$h" -n "$ns" --type=merge -p "{\"spec\":{\"minReplicas\":$m,\"maxReplicas\":$mx}}" >/dev/null || true; done; restore=(); }
  trap restore_min EXIT
  for node in "${order[@]}"; do
    $KUBECTL cordon "$node"
    mapfile -t mine < <(serving_on "$node")
    for row in "${mine[@]}"; do   # make: start exactly the replacements, then break exactly the pods they replace
      read -r ns h dep k <<< "$row"
      hj=$($KUBECTL get hpa "$h" -n "$ns" -o json)
      m=$(echo "$hj" | jq '.spec.minReplicas // 1'); mx=$(echo "$hj" | jq '.spec.maxReplicas')
      cur=$($KUBECTL get deployment "$dep" -n "$ns" -o jsonpath='{.spec.replicas}'); cur=${cur:-0}
      sel=$($KUBECTL get deployment "$dep" -n "$ns" -o json | jq -r '.spec.selector.matchLabels | to_entries | map("\(.key)=\(.value)") | join(",")')
      goal=$(( cur + k )); (( goal > mx )) && goal=$mx
      restore+=("$ns $h $m $mx")
      if (( goal > cur )); then
        $KUBECTL patch hpa "$h" -n "$ns" --type=merge -p "{\"spec\":{\"minReplicas\":$goal}}" >/dev/null
        for i in $(seq 1 45); do   # up to 90 s for the replacements to be ready elsewhere
          r=$($KUBECTL get deployment "$dep" -n "$ns" -o jsonpath='{.status.readyReplicas}'); (( ${r:-0} >= goal )) && break
          sleep 2
        done
        # break: the pods on this machine go first, and the replica count returns to where it was, so the set shrinks
        # by exactly the pods on this machine and none of them is recreated (controller.kubernetes.io/pod-deletion-cost)
        for pod in $($KUBECTL get pods -n "$ns" -l "$sel" --field-selector "spec.nodeName=$node" -o name); do
          $KUBECTL annotate -n "$ns" "$pod" --overwrite controller.kubernetes.io/pod-deletion-cost=-1000 >/dev/null
        done
        lo=$(( m < cur ? m : cur ))
        $KUBECTL patch hpa "$h" -n "$ns" --type=merge -p "{\"spec\":{\"minReplicas\":$lo,\"maxReplicas\":$cur}}" >/dev/null
        for i in $(seq 1 30); do   # up to 60 s for the machine's pods to leave
          left=$($KUBECTL get pods -n "$ns" -l "$sel" --field-selector "spec.nodeName=$node" --no-headers 2>/dev/null | wc -l)
          (( left == 0 )) && break
          sleep 2
        done
        echo "make before break: $ns/$dep $k replacement(s) ready, $((k - ${left:-0})) pod(s) left $node without eviction"
      fi
    done
    if ! $KUBECTL drain "$node" --ignore-daemonsets --delete-emptydir-data --timeout="${DRAIN_TIMEOUT:-120s}"; then
      echo "drain of $node failed; returning it to service" >&2
      $KUBECTL uncordon "$node"
    fi
    restore_min   # break done: the HPA is free to settle again
  done
fi
echo "schedulable workers: $($KUBECTL get nodes -l '!node-role.kubernetes.io/control-plane' -o json | jq '[.items[] | select(.spec.unschedulable != true)] | length') (wanted $want)"
