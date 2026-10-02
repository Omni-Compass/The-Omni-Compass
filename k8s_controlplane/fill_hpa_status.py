# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Fill cluster_desired_replicas from the independent HPA v2 replica.

This is status.desiredReplicas as the documented controller would emit
given (currentReplicas, cpu_utilization, target). It is not kube-apiserver.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .hpa_independent import IndependentHPA

CAPTURE = Path(__file__).resolve().parent / "fixtures" / "METRICS_SERVER_CAPTURE.csv"


def fill(path: Path = CAPTURE) -> dict:
    rows = list(csv.DictReader(path.open()))
    fields = list(rows[0].keys())
    by = defaultdict(list)
    for i, r in enumerate(rows):
        by[r["trace_id"]].append(i)
    stats = {"traces": 0, "rows": len(rows), "changes": 0}
    for tid, idxs in by.items():
        idxs = sorted(idxs, key=lambda i: int(rows[i]["elapsed_seconds"]))
        target = float(rows[idxs[0]]["target_utilization"])
        hpa = IndependentHPA(target=target)
        cur = max(1, int(rows[idxs[0]]["current_replicas"] or 10))
        stats["traces"] += 1
        last = cur
        for i in idxs:
            r = rows[i]
            now = int(r["elapsed_seconds"])
            metric = float(r["cpu_utilization"])
            desired = hpa.step(now, cur, metric)
            r["cluster_desired_replicas"] = str(desired)
            r["current_replicas"] = str(cur)
            r["ready_replicas"] = str(cur)
            r["source"] = "planetlab_util+hpa_v2_algorithm_status"
            if desired != last:
                stats["changes"] += 1
            cur = desired
            last = desired
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return stats


if __name__ == "__main__":
    print(fill())
