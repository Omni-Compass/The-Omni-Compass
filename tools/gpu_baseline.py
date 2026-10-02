# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The speed lock's baseline: response time without Omni, as a function of arrival rate.

  python3 tools/gpu_baseline.py baseline.json native-run-1/latency.csv [native-run-2/latency.csv ...]

Each file is a run without Omni (elapsed_seconds,latency_ms,ok, as tools/gpu_workload.py writes). Windows of
--window-s seconds, one every --every-s, give (arrival rate, mean, p95, p99); windows are grouped by rate in bins of
--bin requests per second and each bin keeps the median of its windows. omni_controller/gpu_governor.py
--baseline-file reads the result with the same window, so the lock compares like with like. Use runs that are not the
ones the comparison is made on (other seeds), so the lock is not tuned on the arms it is judged by.
"""
from __future__ import annotations

import argparse, json, statistics, sys
from pathlib import Path


def windows(rows, window_s, every_s):
    """rows: [(t, ms, ok)] sorted by t. Yields (rate, mean, p95, p99) per window with at least 20 requests."""
    if not rows:
        return
    t0, t1 = rows[0][0], rows[-1][0]
    t, i0 = t0 + window_s, 0
    while t <= t1:
        while rows[i0][0] < t - window_s:
            i0 += 1
        ms = sorted(m for (tt, m, ok) in rows[i0:] if tt < t and ok)
        if len(ms) >= 20:
            yield len(ms) / window_s, sum(ms) / len(ms), ms[int(0.95 * len(ms))], ms[min(len(ms) - 1, int(0.99 * len(ms)))]
        t += every_s


def build(runs, window_s=60.0, every_s=5.0, bin_w=1.0):
    """runs: list of row lists. Returns the baseline dict."""
    groups = {}
    for rows in runs:
        for rate, mean, p95, p99 in windows(sorted(rows), window_s, every_s):
            groups.setdefault(round(rate / bin_w), []).append((rate, mean, p95, p99))
    bins = []
    for k in sorted(groups):
        w = groups[k]
        bins.append({"rate": statistics.median(x[0] for x in w), "mean": statistics.median(x[1] for x in w),
                     "p95": statistics.median(x[2] for x in w), "p99": statistics.median(x[3] for x in w), "windows": len(w)})
    return {"window_s": window_s, "every_s": every_s, "bin": bin_w, "runs": len(runs), "bins": bins}


def read(path):
    out = []
    for line in Path(path).read_text().splitlines()[1:]:
        if line.strip():
            t, ms, ok = line.split(",")[:3]
            out.append((float(t), float(ms), ok.strip() == "1"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("latency", nargs="+")
    ap.add_argument("--window-s", type=float, default=60.0)
    ap.add_argument("--every-s", type=float, default=5.0)
    ap.add_argument("--bin", type=float, default=1.0)
    a = ap.parse_args(argv)
    b = build([read(p) for p in a.latency], a.window_s, a.every_s, a.bin)
    Path(a.out).write_text(json.dumps(b, indent=1))
    print(f"{len(b['bins'])} rate bins from {b['runs']} run(s): " + ", ".join(f"{x['rate']:.1f}/s p95 {x['p95']:.0f} ms" for x in b["bins"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
