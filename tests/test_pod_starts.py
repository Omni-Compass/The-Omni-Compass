# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Exact pod-start timing from the API server's watch stream (pilot/bench_report.py pod_starts): each serving pod created
in the measured window waits from its creationTimestamp to the moment its Ready condition turned True; a pod not Ready
by the end waits until the end; pods created before the window are not counted; the stream is kubectl's concatenated,
indented JSON events, several per pod."""
import json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from pilot.bench_report import pod_starts


def pod(uid, created, ready=None):
    cond = [{"type": "Ready", "status": "True" if ready else "False", "lastTransitionTime": ready or created}]
    return {"metadata": {"uid": uid, "name": uid, "creationTimestamp": created}, "status": {"conditions": cond}}


def main():
    d = Path(tempfile.mkdtemp())
    t0 = 1790550000
    iso = lambda s: __import__("datetime").datetime.fromtimestamp(t0 + s, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = [{"type": "ADDED", "object": pod("old", iso(-300), iso(-296))},          # before the window: not counted
              {"type": "ADDED", "object": pod("a", iso(10))},
              {"type": "MODIFIED", "object": pod("a", iso(10), iso(13))},            # 3 s
              {"type": "ADDED", "object": pod("b", iso(100))},
              {"type": "MODIFIED", "object": pod("b", iso(100), iso(105))},          # 5 s
              {"type": "MODIFIED", "object": pod("b", iso(100), iso(105))},
              {"type": "ADDED", "object": pod("c", iso(890))}]                       # never Ready: waits to the end (10 s)
    (d / "pod_watch.json").write_text("\n".join(json.dumps(e, indent=4) for e in events) + "\n")
    (d / "window_start.txt").write_text(f"{t0}\n"); (d / "window_end.txt").write_text(f"{t0 + 900}\n")
    g = pod_starts(d)
    assert g == {"pods started": 3.0, "pod start wait, total (s)": 18.0, "pod start wait, mean (s)": 6.0}, g
    assert pod_starts(Path(tempfile.mkdtemp())) == {}, "no stream, no gauge"
    print("pod starts: 3 in the window (3 s, 5 s, 10 s until the end), the one before the window not counted")
    print("PASS test_pod_starts")


if __name__ == "__main__":
    main()
