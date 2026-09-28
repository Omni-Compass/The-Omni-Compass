"""Work served under the closed-loop load (deploy/kind/loadgen.yaml), estimated per repetition.

  python3 tools/closed_loop_estimate.py DIR      # DIR holds bench-<arm>-<rep>/ with latency.csv, capture.csv, load_schedule.log

Each generator sends 20 requests one after another, each waiting for its answer, then sleeps RANDOM % 3 s (mean 1 s).
A generator's cycle is therefore 20 R + 1 s, R the mean response time, and it serves 20 / (20 R + 1) requests a second.
The requests of an arm are that rate times the generator-seconds of the load schedule. R is the mean response time of
the probe's successful requests in the same arm (the same service the generators call). The generators do not count
their requests, so this is an estimate; an open-loop load (LOADGEN=open) or a server-side count replaces it.
Prints, for Omni-Compass on top against native, paired over repetitions: requests, CPU used, CPU per request.
"""
from __future__ import annotations

import csv, json, math, re, statistics, sys
from pathlib import Path

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}


def generator_seconds(d):
    """Generator-seconds over the measured window, from load_schedule.log ("HH:MM:SS load-generator replicas -> r")."""
    steps = []
    for line in (d / "load_schedule.log").read_text().splitlines():
        m = re.match(r"(\d+):(\d+):(\d+) load-generator replicas -> (\d+)", line)
        if m:
            h, mi, s, r = map(int, m.groups()); steps.append((h * 3600 + mi * 60 + s, r))
    rows = list(csv.DictReader(open(d / "capture.csv")))
    t_end = steps[0][0] + float(rows[-1]["elapsed_seconds"]) if rows else steps[-1][0]
    total = 0.0
    for (t0, r), nxt in zip(steps, steps[1:] + [(max(t_end, steps[-1][0]), 0)]):
        t1 = nxt[0] if nxt[0] >= t0 else nxt[0] + 86400
        total += r * (t1 - t0)
    return total


def arm(d):
    ms = [float(r["latency_ms"]) for r in csv.DictReader(open(d / "latency.csv")) if r["ok"] == "1"]
    R = statistics.mean(ms) / 1000.0
    req = generator_seconds(d) * 20.0 / (20.0 * R + 1.0)
    cpu = statistics.mean(float(r["used_cpu_m"]) for r in csv.DictReader(open(d / "capture.csv")))
    return req, cpu


def main(root):
    root = Path(root); pairs = []
    for dn in sorted(root.glob("bench-native-*")):
        rep = dn.name.split("-", 2)[2]; do = root / f"bench-omni-{rep}"
        if do.exists() and (dn / "load_schedule.log").exists() and (do / "load_schedule.log").exists():
            (qn, cn), (qo, co) = arm(dn), arm(do)
            pairs.append((qo / qn - 1, co / cn - 1, (co / qo) / (cn / qn) - 1))
    out = {"repetitions": len(pairs)}
    lines = [f"Closed-loop work estimate, Omni-Compass on top against native, {len(pairs)} paired repetitions (estimate: the generators do not count their requests)"]
    for k, name in enumerate(("requests served", "CPU used", "CPU per request")):
        d = [p[k] for p in pairs]; m = statistics.mean(d)
        h = T95.get(len(d) - 1, 1.96) * statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
        out[name] = {"change": m, "ci95": [m - h, m + h]}
        lines.append(f"  {name:16s} {100 * m:+6.1f}%   95% interval {100 * (m - h):+.1f}% to {100 * (m + h):+.1f}%")
    (root / "CLOSED_LOOP_ESTIMATE.json").write_text(json.dumps(out, indent=1))
    print("\n".join(lines))
    return out


if __name__ == "__main__":
    main(sys.argv[1])
