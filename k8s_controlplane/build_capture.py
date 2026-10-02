# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Build the metrics-server-shaped capture file from vendored PlanetLab traces."""
from __future__ import annotations

import csv
from pathlib import Path

from .trace_replay import load_all, resample_hold

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "fixtures" / "METRICS_SERVER_CAPTURE.csv"
REQUEST_MC = 200.0
REPLICAS = 10
TARGET = 0.70


def main():
    traces = load_all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "trace_id", "elapsed_seconds", "cpu_utilization", "cpu_millicores_avg",
        "request_millicores", "ready_replicas", "current_replicas",
        "cluster_desired_replicas", "target_utilization", "source",
    ]
    n = 0
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for name, series in traces.items():
            util = resample_hold(series / 100.0, 300, 15)
            for i, u in enumerate(util):
                u = max(0.0, float(u))
                w.writerow({
                    "trace_id": name,
                    "elapsed_seconds": i * 15,
                    "cpu_utilization": f"{u:.6f}",
                    "cpu_millicores_avg": f"{u * REQUEST_MC:.3f}",
                    "request_millicores": int(REQUEST_MC),
                    "ready_replicas": REPLICAS,
                    "current_replicas": REPLICAS,
                    "cluster_desired_replicas": "",
                    "target_utilization": TARGET,
                    "source": "planetlab_comon_2011_holdlast_15s",
                })
                n += 1
    print(f"wrote {n} rows, {len(traces)} traces -> {OUT}")


if __name__ == "__main__":
    main()
