# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Repeated live runs: aggregate native / watch (Omni runs, writes nothing) / omni (B) / strict (C) arms over repetitions of scripts/kind_bench.sh.
Per repetition the gauges come from pilot/bench_report.py (capture.csv, latency.csv); across repetitions this reports
means and, for each Omni arm against native, the paired mean difference with a t-based 95% interval (n repetitions).
Usage: python tools/live_reps.py DIR  (DIR holds bench-<arm>-<rep>/)  ->  DIR/LIVE_REPS.md, DIR/LIVE_REPS.json"""
import csv, json, math, re, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from pilot.bench_report import gauges, latency, pod_starts, LOWER_BETTER

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
KEYS = ["worker nodes in service, mean", "node-hours", "energy, parked workers still on at idle power (Wh)", "energy (Wh)", "response time (ms), mean", "response time (ms), 95th percentile",
        "response time (ms), 99th percentile", "time over the response line (% of samples)", "failed requests (%)", "pending pods, pod-minutes", "utilisation (used / allocatable)",
        "CPU used (cores), mean", "Omni's own CPU (cores), mean", "CPU used with Omni's own (cores), mean",
        "energy per core-hour (Wh)", "HPA replicas, mean",
        "pods started", "pod start wait, total (s)", "pod start wait, mean (s)"]


LABEL = {"energy, parked workers still on at idle power (Wh)": "energy, parked workers still on at idle power (Wh, declared model)",
         "energy (Wh)": "energy, parked workers at 25 W standby (Wh, declared model; kind never does this)",
         "energy per core-hour (Wh)": "energy per core-hour (Wh, the 25 W standby model)"}
NEUTRAL = {"CPU used (cores), mean", "utilisation (used / allocatable)", "Omni's own CPU (cores), mean",
           "CPU used with Omni's own (cores), mean"}   # more is not better or worse by itself
NOTE = ["**Energy on kind is a declared model, not a meter.** Every worker stays powered and Ready in every arm; the first",
        "energy row counts a parked worker at its full idle power, which is what kind does. The second counts it at the",
        "declared standby power, which needs a node autoscaler that really removes the machine; this run has none.", ""]


def arm_gauges(d):
    rows = list(csv.DictReader(open(d / "capture.csv")))
    g = gauges(rows); g.update(latency(str(d / "latency.csv"))); g.update(pod_starts(d))
    # the controller's own cost (its process and every command it ran; it runs beside the cluster, not in it), from its
    # audit: counted so a CPU saving in the cluster is never reported without what Omni itself spent. Native: 0.
    own = 0.0
    if "-native-" not in d.name and (d / "audit.jsonl").exists():
        for line in open(d / "audit.jsonl"):
            if '"overhead"' in line:
                own = float(json.loads(line)["overhead"].get("cores_mean", 0.0))
        if own == 0.0:
            own = float("nan")        # an Omni arm without its cost record: unknown, never zero
    elif "-native-" not in d.name:
        own = float("nan")
    g["Omni's own CPU (cores), mean"] = own
    g["CPU used with Omni's own (cores), mean"] = g.get("CPU used (cores), mean", float("nan")) + own
    return g


FAULTS = (("machine down", "machine back"), ("spike:", "spike over"), ("runaway pod started", "runaway pod removed"),
          ("probe blind", "probe back"))


def fault_windows(d, slo):
    """Per fault in this run (faults.log, scripts/kind_faults.sh): time to recover (until 30 s straight under the line,
    from the fault's start, at most 300 s) and the share of samples over the line or failed in the 300 s after it."""
    import os
    try:
        t0 = float(open(d / "window_start.txt").read().split()[0])
        rows = list(csv.DictReader(open(d / "latency.csv")))
        ev = [(float(l.split()[0]), l.split(" ", 1)[1].strip()) for l in open(d / "faults.log") if l.strip()]
    except (OSError, ValueError, IndexError):
        return {}
    smp = [(t0 + float(r["elapsed_seconds"]), r.get("ok") == "1" and float(r["latency_ms"]) <= slo) for r in rows]
    out = {}
    for start_key, _ in FAULTS:
        st = [t for t, txt in ev if txt.startswith(start_key)]
        if not st:
            continue
        s0 = st[0]
        win = [(t, good) for t, good in smp if s0 <= t <= s0 + 300]
        over = 100.0 * sum(1 for _, g in win if not g) / max(len(win), 1)
        rec, run_start = 300.0, None
        for t, g in win:
            if g:
                run_start = t if run_start is None else run_start
                if t - run_start >= 30:
                    rec = max(0.0, run_start - s0); break
            else:
                run_start = None
        out[start_key.rstrip(":")] = {"recover_s": rec, "over_pct": over}
    return out


def fault_table(root, cols):
    import os
    slo = float(os.environ.get("SLO_MS", 500))
    per = {}
    for d in sorted(root.glob("bench-*-*")):
        _, arm, rep = d.name.split("-", 2)
        w = fault_windows(d, slo)
        if w:
            per.setdefault(arm, {})[rep] = w
    if "native" not in per:
        return []
    L = ["## The fault test: the same faults at the same moments in every arm", "",
         "Time to recover: from the fault's start until responses stay under the line for 30 seconds straight (at most 300 s). "
         "Over the line: the share of response samples over the line or failed in the 300 seconds after the fault. Paired "
         "means over the repetitions; lower is better in both.", "",
         "| Fault | Arm | Time to recover (s) | Over the line (%) | Change in recovery against native |", "|---|---|---:|---:|---:|"]
    for f, _ in FAULTS:
        k = f.rstrip(":")
        for a in [c for c in cols if c in per]:
            reps = sorted(set(per[a]) & set(per["native"]))
            vals = [(per[a][r][k], per["native"][r][k]) for r in reps if k in per[a][r] and k in per["native"][r]]
            if not vals:
                continue
            rec = np.mean([v[0]["recover_s"] for v in vals]); ovr = np.mean([v[0]["over_pct"] for v in vals])
            base = np.mean([v[1]["recover_s"] for v in vals])
            ch = "" if a == "native" else (f"{(rec - base):+.0f} s" + (f" ({(rec - base) / base * 100:+.0f}%)" if base > 0 else ""))
            L.append(f"| {k} | {a} | {rec:.0f} | {ovr:.1f} | {ch} |")
    return L + [""]


def main(root):
    root = Path(root); runs = {}
    for d in sorted(root.glob("bench-*-*")):
        _, arm, rep = d.name.split("-", 2)
        if (d / "capture.csv").exists() and not (d / "INVALID").exists():
            runs.setdefault(arm, {})[rep] = arm_gauges(d)
    out = {"repetitions": {a: sorted(r) for a, r in runs.items()}, "means": {}, "paired": {}}
    for a, r in runs.items():
        out["means"][a] = {k: float(np.nanmean([g.get(k, np.nan) for g in r.values()])) for k in KEYS}
    L = ["# Repeated live runs on kind (native vs Omni watching only vs Omni on top vs Omni alone)", ""]
    tuned = sorted((a for a in runs if re.fullmatch(r"native\d+", a)), key=lambda a: -int(a[6:]))
    cols = [a for a in ("native",) if a in runs] + tuned + [a for a in ("watch", "omni", "bowl", "strict") if a in runs]
    names = {"native": "Native", "watch": "Omni watches only", "omni": "Omni on top", "bowl": "Omni on top, bowl law", "strict": "Omni alone",
             **{a: f"Native tuned, HPA target {a[6:]}" for a in tuned}}
    L += ["## All columns, mean over repetitions", "", "| Gauge | " + " | ".join(names[a] for a in cols) + " |",
          "|---|" + "---:|" * len(cols)]
    L += [f"| {LABEL.get(k, k)} | " + " | ".join(f"{out['means'][a][k]:.4g}" for a in cols) + " |" for k in KEYS]
    L += [""] + NOTE
    for a in ("watch", "omni", "bowl", "strict"):
        if a not in runs or "native" not in runs:
            continue
        reps = sorted(set(runs[a]) & set(runs["native"]))
        out["paired"][a] = {}
        title = {"watch": "W: Omni-Compass watches only (dry run: the cost of being there)", "omni": "B: Omni-Compass on top", "bowl": "B with the bowl law: Omni-Compass on top, push and pull on the HPA target and the node pool",
                 "strict": "C: Omni-Compass decides (strict)"}[a]
        L += [f"## {title} vs native, {len(reps)} paired repetitions", "",
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
            ch = (ob - nb) / abs(nb) * 100 if abs(nb) > 1e-12 else None
            out["paired"][a][k] = {"native": nb, "omni": ob, "diff": float(d.mean()), "ci95": [float(d.mean() - half), float(d.mean() + half)], "significant": bool(sig)}
            ch_s = f"{ch:+.1f}%" if ch is not None else f"{ob - nb:+.3g} (native is 0)"
            L.append(f"| {LABEL.get(k, k)} | {nb:.4g} | {ob:.4g} | {ch_s} | {d.mean() - half:+.4g} to {d.mean() + half:+.4g} | "
                     f"{(('yes, more' if d.mean() > 0 else 'yes, less') if k in NEUTRAL else ('yes, better' if better else 'yes, worse')) if sig else 'no'} |")
        L.append("")
    if tuned and "native" in runs and any(a in runs for a in ("omni", "bowl")):
        # the cost to match: native tuned harder by its operator (a lower HPA target, more pods) against native with
        # Omni-Compass on top, at the same work; the cheapest native setting that reaches Omni-Compass's p95, and what
        # it costs over Omni-Compass
        P95, P99 = "response time (ms), 95th percentile", "response time (ms), 99th percentile"
        CPU, REP, NODES = "CPU used with Omni's own (cores), mean", "HPA replicas, mean", "worker nodes in service, mean"
        m = out["means"]
        L += ["## The cost to match: native tuned harder by its operator, against native with Omni-Compass on top", "",
              "Kubernetes alone with its HPA target lowered (more pods, faster answers), as an operator would tune it without "
              "Omni-Compass, against the same Kubernetes with Omni-Compass on top. Same work in every arm; means over the "
              "repetitions.", "",
              "| Arm | p95 (ms) | p99 (ms) | HPA replicas | CPU used incl. Omni's own (cores) | Machines in service |",
              "|---|---:|---:|---:|---:|---:|"]
        for a in cols:
            if a in ("watch", "strict"):
                continue
            L.append(f"| {names[a]} | {m[a][P95]:.4g} | {m[a][P99]:.4g} | {m[a][REP]:.4g} | {m[a][CPU]:.4g} | {m[a][NODES]:.4g} |")
        L.append("")
        out["cost_to_match"] = {}
        for o in ("bowl", "omni"):
            if o not in runs:
                continue
            match = [a for a in ["native"] + tuned if m[a][P95] <= m[o][P95]]
            if not match:
                L.append(f"- {names[o]} (p95 {m[o][P95]:.4g} ms): no native setting tried reached it; the lowest native p95 "
                         f"is {min(m[a][P95] for a in ['native'] + tuned):.4g} ms ({names[min(['native'] + tuned, key=lambda a: m[a][P95])]}).")
                out["cost_to_match"][o] = None
                continue
            best = min(match, key=lambda a: m[a][CPU])
            extra = lambda k: (m[best][k] - m[o][k]) / m[o][k] * 100 if m[o][k] else float("nan")
            L.append(f"- To match {names[o]} (p95 {m[o][P95]:.4g} ms), the cheapest native setting is {names[best]} "
                     f"(p95 {m[best][P95]:.4g} ms): {extra(REP):+.1f}% HPA replicas, {extra(CPU):+.1f}% CPU including "
                     f"Omni-Compass's own, {extra(NODES):+.1f}% machines in service, against native with Omni-Compass on top.")
            out["cost_to_match"][o] = {"native_setting": best, "replicas_pct": extra(REP), "cpu_pct": extra(CPU), "machines_pct": extra(NODES)}
        L.append("")
    faults = fault_table(root, cols)
    if faults:
        L += faults
    (root / "LIVE_REPS.json").write_text(json.dumps(out, indent=1)); (root / "LIVE_REPS.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
