# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The cost to match (tools/live_reps.py): native tuned harder by its operator (HPA target 40, 30, 20) against native
with Omni-Compass on top. With stand-in gauges, the report lists every arm, picks the cheapest native setting whose p95
reaches Omni-Compass's, and states what it costs over Omni-Compass; when no native setting reaches it, it says so."""
import sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import tools.live_reps as LR

G = {  # arm -> (p95, p99, replicas, cpu incl. Omni's own, machines)
    "native": (380, 590, 8.8, 1.00, 6.0), "native40": (300, 480, 10.5, 1.10, 6.0), "native30": (190, 300, 13.0, 1.30, 6.0),
    "native20": (120, 190, 17.0, 1.60, 6.0), "bowl": (132, 186, 8.4, 1.02, 5.7)}


def fake(d):
    arm = d.name.split("-", 2)[1]
    p95, p99, rep, cpu, nodes = G[arm]
    rep_n = int(d.name.split("-", 2)[2])
    j = 0.01 * rep_n                                  # a little spread between repetitions
    g = {k: 0.0 for k in LR.KEYS}
    g.update({"response time (ms), 95th percentile": p95 + j, "response time (ms), 99th percentile": p99 + j,
              "HPA replicas, mean": rep + j, "CPU used with Omni's own (cores), mean": cpu + j / 100,
              "worker nodes in service, mean": nodes})
    return g


def main():
    t = Path(tempfile.mkdtemp())
    for arm in G:
        for r in (1, 2, 3):
            d = t / f"bench-{arm}-{r}"; d.mkdir(); (d / "capture.csv").write_text("x\n")
    LR.arm_gauges = fake
    LR.main(str(t))
    md = (t / "LIVE_REPS.md").read_text()
    assert "The cost to match" in md and "Native tuned, HPA target 20" in md
    import json
    out = json.loads((t / "LIVE_REPS.json").read_text())
    c = out["cost_to_match"]["bowl"]
    assert c["native_setting"] == "native20", c                       # the only native setting at or under 132 ms
    assert abs(c["replicas_pct"] - (17.0 - 8.4) / 8.4 * 100) < 1.0 and c["cpu_pct"] > 50
    G["native20"] = (140, 200, 17.0, 1.60, 6.0)                       # now no native setting reaches the bowl
    for r in (1, 2, 3):
        (t / f"bench-native20-{r}" / "capture.csv").write_text("x\n")
    LR.main(str(t))
    assert json.loads((t / "LIVE_REPS.json").read_text())["cost_to_match"]["bowl"] is None
    assert "no native setting tried reached it" in (t / "LIVE_REPS.md").read_text()
    # the fault table: one run per arm, a fault at t0+100 s; native stays over the line 120 s, Omni 30 s
    import time as _t
    f = Path(tempfile.mkdtemp())
    for arm, bad in (("native", 120), ("bowl", 30)):
        d = f / f"bench-{arm}-1"; d.mkdir()
        (d / "window_start.txt").write_text("1000\n")
        rows = ["elapsed_seconds,latency_ms,ok"] + [f"{t},{900 if 100 <= t < 100 + bad else 100},1" for t in range(0, 600, 5)]
        (d / "latency.csv").write_text("\n".join(rows) + "\n")
        (d / "faults.log").write_text("1100 machine down: kind-worker6\n1220 machine back: kind-worker6\n")
    tab = "\n".join(LR.fault_table(f, ["native", "bowl"]))
    assert "| machine down | native | 120 |" in tab and "| machine down | bowl | 30 |" in tab and "-90 s" in tab, tab
    print("PASS cost to match: every arm listed, the cheapest native setting that reaches Omni-Compass's p95 and its extra "
          "pods, CPU and machines, and a plain statement when none reaches it; fault recovery times paired against native")


if __name__ == "__main__":
    main()
