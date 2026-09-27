#!/usr/bin/env bash
# Node-pool actuator for a kind cluster: keep exactly N worker nodes schedulable.
# Scale-down cordons and drains specific workers so their pods are rescheduled; scale-up uncordons parked workers.
# Which workers: fewest serving pods first (pods of a Deployment an HPA scales), then fewest pods, so an empty worker is
# always given back before one that serves traffic.
# Make before break: when a worker does carry serving pods, the replacements start first. After the cordon, the HPA's
# minReplicas is raised by the number of serving pods on that worker, the drain waits until the Deployment has that many
# more ready replicas (on the other workers), and only then evicts; minReplicas is restored afterwards (also on exit).
# So capacity never dips below what was serving (live set 9: a drain that evicted one of two pods doubled the load on
# the other while its replacement started). Drains go through the eviction API, so PodDisruptionBudgets are honoured: a
# drain that would take the last ready replica times out after DRAIN_TIMEOUT and the node goes back into service.
# A parked kind node is still a running container: it is counted as off because it
# carries no workload, as a removed node in a cloud node pool would. Usage: bash scripts/kind_nodepool.sh N
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
  restore_min() { for r in "${restore[@]}"; do read -r ns h m <<< "$r"; $KUBECTL patch hpa "$h" -n "$ns" --type=merge -p "{\"spec\":{\"minReplicas\":$m}}" >/dev/null || true; done; restore=(); }
  trap restore_min EXIT
  for node in "${order[@]}"; do
    $KUBECTL cordon "$node"
    mapfile -t mine < <(serving_on "$node")
    for row in "${mine[@]}"; do   # make: start the replacements on the other workers first
      read -r ns h dep k <<< "$row"
      hj=$($KUBECTL get hpa "$h" -n "$ns" -o json)
      m=$(echo "$hj" | jq '.spec.minReplicas // 1'); mx=$(echo "$hj" | jq '.spec.maxReplicas')
      ready0=$($KUBECTL get deployment "$dep" -n "$ns" -o jsonpath='{.status.readyReplicas}'); ready0=${ready0:-0}
      goal=$(( ready0 + k )); (( goal > mx )) && goal=$mx
      restore+=("$ns $h $m")
      if (( goal > m )); then
        $KUBECTL patch hpa "$h" -n "$ns" --type=merge -p "{\"spec\":{\"minReplicas\":$goal}}" >/dev/null
      fi
      for i in $(seq 1 45); do   # up to 90 s for the replacements to be ready
        r=$($KUBECTL get deployment "$dep" -n "$ns" -o jsonpath='{.status.readyReplicas}'); (( ${r:-0} >= goal )) && break
        sleep 2
      done
      echo "make before break: $ns/$dep ready ${r:-0} of $goal before draining $node"
    done
    if ! $KUBECTL drain "$node" --ignore-daemonsets --delete-emptydir-data --timeout="${DRAIN_TIMEOUT:-120s}"; then
      echo "drain of $node failed; returning it to service" >&2
      $KUBECTL uncordon "$node"
    fi
    restore_min   # break done: the HPA is free to settle again
  done
fi
echo "schedulable workers: $($KUBECTL get nodes -l '!node-role.kubernetes.io/control-plane' -o json | jq '[.items[] | select(.spec.unschedulable != true)] | length') (wanted $want)"
