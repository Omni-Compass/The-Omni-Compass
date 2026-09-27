#!/usr/bin/env bash
# Cluster capture for the Omni-Compass fleet harness. Read-only: uses get/top only.
# Requires kubectl (with metrics-server) and jq. Optional: POWER_CMD printing site power in watts.
# ACTIVE_ONLY=1 counts only nodes in service (open to work, or cordoned but still carrying work), and the usage on them.
# Usage: OUT=capture.csv INTERVAL=15 DURATION=21600 [POWER_CMD="..."] [ACTIVE_ONLY=1] bash kube_capture.sh
set -euo pipefail
OUT="${OUT:-capture.csv}"; INTERVAL="${INTERVAL:-15}"; DURATION="${DURATION:-21600}"
to_m() { awk '{v=$1; if (v ~ /m$/) {sub(/m$/,"",v); print v+0} else if (v ~ /n$/) {sub(/n$/,"",v); print v/1000000} else print v*1000}'; }
echo "timestamp,elapsed_seconds,nodes_ready,nodes_total,alloc_cpu_m,req_cpu_m,used_cpu_m,pods_pending,hpa_count,hpa_current_replicas,hpa_desired_replicas,power_w" > "$OUT"
start=$(date +%s)
while :; do
  now=$(date +%s); el=$((now - start)); [ "$el" -gt "$DURATION" ] && break
  nodes=$(kubectl get nodes -o json)
  pods=$(kubectl get pods -A -o json)
  if [ "${ACTIVE_ONLY:-0}" = "1" ]; then
    # in service: open to new work, or closed (idle mark or cordon) but still carrying work (not a DaemonSet's)
    carrying=$(echo "$pods" | jq -r '[.items[] | select(.status.phase=="Running" or .status.phase=="Pending")
      | select(all(.metadata.ownerReferences[]?; .kind != "DaemonSet")) | .spec.nodeName // empty] | unique | join(" ")')
    nodes=$(echo "$nodes" | jq --arg c " $carrying " '.items |= map(select(
      ((.spec.unschedulable == true or any(.spec.taints[]?; .key == "omnicompass.io/idle")) as $closed
       | ($closed | not) and ([.spec.taints[]? | select(.effect=="NoSchedule")] | length) == 0
         or (.metadata.name as $n | $closed and ($c | contains(" " + $n + " "))))))')
  fi
  names=$(echo "$nodes" | jq -r '[.items[].metadata.name] | join(" ")')
  ready=$(echo "$nodes" | jq '[.items[] | select(any(.status.conditions[]; .type=="Ready" and .status=="True"))] | length')
  total=$(echo "$nodes" | jq '.items | length')
  alloc=$(echo "$nodes" | jq -r '.items[].status.allocatable.cpu' | to_m | awk '{s+=$1} END {printf "%.0f", s}')
  req=$(echo "$pods" | jq -r '.items[] | select(.status.phase=="Running") | .spec.containers[].resources.requests.cpu // "0"' | to_m | awk '{s+=$1} END {printf "%.0f", s}')
  pending=$(echo "$pods" | jq '[.items[] | select(.status.phase=="Pending")] | length')
  used=$(kubectl top nodes --no-headers 2>/dev/null | awk -v names="$names" 'BEGIN{n=split(names,a," "); for(i=1;i<=n;i++) on[a[i]]=1} ($1 in on){print $2}' | to_m | awk '{s+=$1} END {printf "%.0f", s}')
  hpa=$(kubectl get hpa -A -o json)
  hc=$(echo "$hpa" | jq '.items | length'); hcur=$(echo "$hpa" | jq '[.items[].status.currentReplicas // 0] | add // 0'); hdes=$(echo "$hpa" | jq '[.items[].status.desiredReplicas // 0] | add // 0')
  pw=""; if [ -n "${POWER_CMD:-}" ]; then pw=$(eval "$POWER_CMD" 2>/dev/null || echo ""); fi
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),$el,$ready,$total,$alloc,$req,$used,$pending,$hc,$hcur,$hdes,$pw" >> "$OUT"
  sleep "$INTERVAL"
done
