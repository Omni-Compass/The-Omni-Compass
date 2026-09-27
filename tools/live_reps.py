"""Repeated live runs: aggregate native / omni (B) / strict (C) arms over repetitions of scripts/kind_bench.sh.
Per repetition the gauges come from pilot/bench_report.py (capture.csv, latency.csv); across repetitions this reports
means and, for each Omni arm against native, the paired mean difference with a t-based 95% interval (n repetitions).
Usage: python tools/live_reps.py DIR  (DIR holds bench-<arm>-<rep>/)  ->  DIR/LIVE_REPS.md, DIR/LIVE_REPS.json"""
import csv, json, math, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from pilot.bench_report import gauges, latency, LOWER_BETTER

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
KEYS = ["worker nodes in service, mean", "node-hours", "energy (Wh)", "response time (ms), mean", "response time (ms), 95th percentile",
        "response time (ms), 99th percentile", "failed requests (%)", "pending pods, pod-minutes", "utilisation (used / allocatable)"]


def arm_gauges(d):
    rows = list(csv.DictReader(open(d / "capture.csv")))
    g = gauges(rows); g.update(latency(str(d / "latency.csv")))
    return g


def main(root):
    root = Path(root); runs = {}
    for d in sorted(root.glob("bench-*-*")):
        _, arm, rep = d.name.split("-", 2)
        if (d / "capture.csv").exists():
            runs.setdefault(arm, {})[rep] = arm_gauges(d)
    out = {"repetitions": {a: sorted(r) for a, r in runs.items()}, "means": {}, "paired": {}}
    for a, r in runs.items():
        out["means"][a] = {k: float(np.nanmean([g.get(k, np.nan) for g in r.values()])) for k in KEYS}
    L = ["# Repeated live runs on kind (native vs Omni on top vs Omni alone)", ""]
    for a in ("omni", "strict"):
        if a not in runs or "native" not in runs:
            continue
        reps = sorted(set(runs[a]) & set(runs["native"]))
        out["paired"][a] = {}
        L += [f"## {'B: Omni-Compass on top' if a == 'omni' else 'C: Omni-Compass decides (strict)'} vs native, {len(reps)} paired repetitions", "",
              "| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |", "|---|---:|---:|---:|---:|---|"]
        for k in KEYS:
            d = np.array([runs[a][r].get(k, np.nan) - runs["native"][r].get(k, np.nan) for r in reps], float)
            d = d[~np.isnan(d)]
            if len(d) == 0:
                continue
            nb = float(np.nanmean([runs["native"][r].get(k, np.nan) for r in reps])); ob = nb + float(d.mean())
            half = T95.get(len(d) - 1, 1.96) * (d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 1 else float("nan")
            sig = len(d) > 1 and (d.mean() - half > 0 or d.mean() + half < 0)
            better = (d.mean() < 0) == (k in LOWER_BETTER)
            ch = (ob - nb) / abs(nb) * 100 if abs(nb) > 1e-12 else 0.0
            out["paired"][a][k] = {"native": nb, "omni": ob, "diff": float(d.mean()), "ci95": [float(d.mean() - half), float(d.mean() + half)], "significant": bool(sig)}
            L.append(f"| {k} | {nb:.4g} | {ob:.4g} | {ch:+.1f}% | {d.mean() - half:+.4g} to {d.mean() + half:+.4g} | "
                     f"{('yes, better' if better else 'yes, worse') if sig else 'no'} |")
        L.append("")
    (root / "LIVE_REPS.json").write_text(json.dumps(out, indent=1)); (root / "LIVE_REPS.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
