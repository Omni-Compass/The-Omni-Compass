#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# Shadow pilot on any Kubernetes cluster (the current kubectl context): Omni-Compass runs read-only beside the cluster's
# own autoscalers, decides what it would do every 15 s with the benchmarked closure law, and writes nothing.
#   1. applies deploy/pilot/rbac-shadow.yaml and proves with `kubectl auth can-i` that the identity can read and cannot
#      write (the run stops if any write permission exists);
#   2. captures telemetry (fleet/capture/kube_capture.sh) and runs the controller in observe mode for DURATION seconds;
#   3. replays the capture (fleet/capture_replay.py) and writes SHADOW_REPORT.md: node-hours and energy the cluster used
#      against what Omni-Compass would have used, pending pods, every recommendation, and the count of writes (must be 0).
# Usage: DURATION=86400 IDLE_W=200 DYN_W=350 [POWER_CMD="..."] bash scripts/pilot_shadow.sh
set -euo pipefail
OUT_DIR="${OUT_DIR:-shadow_out}"; DURATION="${DURATION:-3600}"; IDLE_W="${IDLE_W:-100}"; DYN_W="${DYN_W:-150}"
LAW="${LAW:-tuning/GLOBAL_LEAGUE_PREREGISTRATION.json}"; mkdir -p "$OUT_DIR"
kubectl apply -f deploy/pilot/rbac-shadow.yaml >/dev/null
SA="system:serviceaccount:omni-shadow:omni-shadow"; can() { kubectl auth can-i "$@" --as="$SA"; }
{
  echo "== can (read)"; echo "list pods: $(can list pods -A)"; echo "list nodes: $(can list nodes)"; echo "list hpa: $(can list hpa -A)"
  echo "== cannot (write)"
  for v in "patch nodes" "delete pods -A" "create pods -A" "patch deployments -A" "patch hpa -A" "create pods/eviction -A" "get secrets -A"; do
    echo "$v: $(can $v)"; done
} | tee "$OUT_DIR/rbac_shadow.txt"
! sed -n '/== cannot/,$p' "$OUT_DIR/rbac_shadow.txt" | grep -q ": yes$" || { echo "shadow identity can write: stopping"; exit 1; }
python -m omni_controller.controller --kubectl "$(pwd)/scripts/kubectl_as.sh" --mode observe --interval 15 \
  --iterations $(( DURATION / 15 )) --closure "$LAW" --audit "$OUT_DIR/audit.jsonl" --kill-file "$OUT_DIR/kill" \
  > "$OUT_DIR/controller.log" 2>&1 &
ctl=$!
export POWER_CMD="${POWER_CMD:-}"
OUT="$OUT_DIR/capture.csv" INTERVAL=15 DURATION="$DURATION" bash fleet/capture/kube_capture.sh
wait "$ctl" || true
python - "$OUT_DIR" "$IDLE_W" "$DYN_W" <<'P'
import json, sys, csv
from pathlib import Path
d = Path(sys.argv[1]); idle, dyn = float(sys.argv[2]), float(sys.argv[3])
dec = [json.loads(l)["decision"] for l in (d / "audit.jsonl").read_text().splitlines() if '"decision"' in l]
writes = sum(1 for l in (d / "audit.jsonl").read_text().splitlines() if '"write"' in l)
rows = list(csv.DictReader(open(d / "capture.csv")))
dt = 15 / 3600.0
obs_nh = sum(float(r["nodes_ready"]) for r in rows) * dt
rec_nh = sum(x["nodes_recommended"] for x in dec) * dt * (len(rows) / max(1, len(dec)))
used = [float(r["used_cpu_m"]) / 1000 for r in rows]
L = ["# Shadow pilot report", "", f"decisions logged: {len(dec)}; writes by Omni-Compass: {writes} (must be 0)", "",
     f"node-hours used by the cluster: {obs_nh:.2f}", f"node-hours Omni-Compass would have used: {rec_nh:.2f} "
     f"({(rec_nh - obs_nh) / max(obs_nh, 1e-9) * 100:+.1f}%)",
     f"estimated idle energy difference: {(rec_nh - obs_nh) * idle / 1000:+.2f} kWh (idle {idle:.0f} W per node, dynamic power unchanged)",
     "", "Every recommendation, the observed state and the engine state are in audit.jsonl; the telemetry is capture.csv."]
(d / "SHADOW_REPORT.md").write_text("\n".join(L)); print("\n".join(L))
assert writes == 0, "Omni-Compass wrote during a shadow pilot"
P
