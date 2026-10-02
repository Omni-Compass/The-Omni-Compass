#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# Capture metrics-server + HPA status from a live cluster (kind, k3s, or any kubeconfig).
# This environment has no kind/kubectl; run this where you have a cluster.
#
# Output schema matches traces/metrics_server_schema.csv
set -euo pipefail
NS=${NS:-default}
NAME=${NAME:-}
OUT=${OUT:-metrics_server_capture.csv}
INTERVAL=${INTERVAL:-15}
echo "timestamp,elapsed_seconds,namespace,hpa,desired_replicas,current_replicas,ready_replicas,cpu_millicores_avg,cpu_utilization,target_utilization" > "$OUT"
start=$(date +%s)
if ! command -v kubectl >/dev/null; then
  echo "kubectl not found. This script is the live-cluster capture contract, not a simulator." >&2
  exit 2
fi
if [[ -z "$NAME" ]]; then
  NAME=$(kubectl -n "$NS" get hpa -o jsonpath='{.items[0].metadata.name}')
fi
echo "capturing HPA $NS/$NAME every ${INTERVAL}s -> $OUT"
while true; do
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  el=$(( $(date +%s) - start ))
  line=$(kubectl -n "$NS" get hpa "$NAME" -o json | python3 -c "
import json,sys
h=json.load(sys.stdin)
st=h.get('status',{})
spec=h.get('spec',{})
desired=st.get('desiredReplicas')
current=st.get('currentReplicas')
target=None
for m in spec.get('metrics') or []:
    r=m.get('resource') or {}
    t=(r.get('target') or {})
    if t.get('averageUtilization') is not None:
        target=t['averageUtilization']
util=None
mcores=None
for m in st.get('currentMetrics') or []:
    r=m.get('resource') or {}
    if r.get('name')=='cpu':
        cur=r.get('current') or {}
        util=cur.get('averageUtilization')
        v=cur.get('averageValue')
        if isinstance(v,str) and v.endswith('m'):
            mcores=float(v[:-1])
        elif v:
            mcores=float(v)*1000
ready=current
print(f\"{desired},{current},{ready},{mcores},{util},{target}\")
")
  echo "$now,$el,$NS,$NAME,$line" >> "$OUT"
  sleep "$INTERVAL"
done
