#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The KWOK scale table (scripts/kwok_scale.sh, .github/workflows/kwok-scale.yml): one row per cluster size.

  python3 tools/kwok_report.py DIR     DIR holds kwok-<n>/KWOK.json (one per size)
"""
import json, sys
from pathlib import Path


def main(d):
    rows = sorted((json.loads(p.read_text()) for p in Path(d).glob("*/KWOK.json")), key=lambda r: r["nodes"])
    print("# Omni-Compass on a real Kubernetes control plane at scale (KWOK nodes)\n")
    print("Real Node, Pod, Deployment and HPA objects in a real API server; the nodes are KWOK nodes with no machines "
          "behind them (evidence class L for the control plane, not for energy or a workload).\n")
    print("| Nodes | Ready | Decisions | Decision time, median (ms) | Decision time, max (ms) | Controller CPU (cores, mean) "
          "| Controller memory, peak (MB) | Node commands | Master switch: everything handed back |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        dm = r["decision_ms"]
        print(f"| {r['nodes']} | {r['nodes_ready']} | {r['decisions']} | {dm['median']} | {dm['max']} | "
              f"{r['controller_cores_mean']} | {r['controller_max_rss_mb']} | {r['node_commands']} | "
              f"{'yes' if r['handed_back'] else 'NO: ' + r['hpa_targets_after'] + ' / closed ' + str(r['nodes_closed_after'])} |")


if __name__ == "__main__":
    main(sys.argv[1])
