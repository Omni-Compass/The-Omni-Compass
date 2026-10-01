# Omni-Compass shadow pilot kit

What a customer runs first. Omni-Compass watches the cluster read-only beside its own autoscalers. Every 15 seconds it
decides what it would do, using the same closure law that was benchmarked. It never writes.

1. `kubectl config use-context <the cluster>`
2. `DURATION=86400 IDLE_W=<watts per idle node> DYN_W=<watts at full load> bash scripts/pilot_shadow.sh`
   - It proves with `kubectl auth can-i` that the identity can read and cannot write, and stops if any write permission
     exists.
   - It captures telemetry and logs every recommendation to `shadow_out/audit.jsonl`.
   - It writes `shadow_out/SHADOW_REPORT.md`: node-hours used against node-hours Omni-Compass would have used, and the
     write count, which must be 0.
3. Scoring against a matched baseline: `python pilot/score.py --baseline baseline.csv --omni omni.csv` (bootstrap
   intervals over hourly blocks).

Guarded control follows `docs/PILOT_PROTOCOL.md`: one loop at a time, the kill switch tested at each handover.

The kit is exercised end to end on kind by the `live-shadow` workflow.
