"""The GPU bench table (scripts/gpu_paired.sh): native / watch (Omni runs, writes nothing) / omni (Omni writes power limits).

Every energy number comes from the device: joules = the time integral of nvidia-smi power.draw over the measured window
(trapezoid rule on its own sample timestamps), summed over the measured GPUs; the CPU package joules come from RAPL
energy counters when the machine has them. Nothing here is a model.

Per repetition, per arm: energy, joules per served request, mean power, peak and mean temperature, served and not
served requests, response time (mean, 95th, 99th percentile), power-limit writes. Across repetitions: for watch and omni
against native, the paired mean difference with a t-based 95% interval. A difference is proven when that interval
excludes zero; otherwise the table says not proven.

The run is INVALID (exit 2) when: a native or watch arm saw a power limit other than the one read at start, the watch
arm executed a write, or an arm ended with a limit that differs from the start (the kill switch did not restore).
Usage: python tools/gpu_reps.py RUN_DIR   (RUN_DIR holds rep-<n>/<arm>/)  ->  RUN_DIR/GPU_REPS.md, RUN_DIR/GPU_REPS.json"""
from __future__ import annotations

import csv, datetime as dt, json, math, sys
from pathlib import Path

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201,
       12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
LOWER = {"energy, whole machine at the wall (J)", "energy, GPU (J)", "energy per served request (J)", "power, GPU mean (W)", "temperature, peak (C)",
         "temperature, mean (C)", "requests not served", "response time, mean (ms)", "response time, 95th percentile (ms)",
         "response time, 99th percentile (ms)", "energy, CPU package (J)"}
PRIMARY = "work per energy (served requests per kJ)"
WALL = "work per wall energy (served requests per kJ, whole machine)"
KEYS = [PRIMARY, WALL, "energy, whole machine at the wall (J)", "energy, GPU (J)", "energy per served request (J)", "power, GPU mean (W)", "requests served", "requests not served",
        "response time, mean (ms)", "response time, 95th percentile (ms)", "response time, 99th percentile (ms)",
        "temperature, peak (C)", "temperature, mean (C)", "energy, CPU package (J)"]


def smi_time(s):
    s = s.strip()
    for f in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(s, f).replace(tzinfo=dt.timezone.utc).timestamp()
        except ValueError:
            pass
    raise ValueError(s)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float("nan")


def arm(d, gpus):
    t0 = float((d / "window_start.txt").read_text().split()[0]); t1 = float((d / "window_end.txt").read_text().split()[0])
    series = {}
    for r in csv.reader(open(d / "smi.csv")):
        if len(r) < 6 or not r[1].strip().isdigit():
            continue
        g = int(r[1])
        if g not in gpus:
            continue
        t = smi_time(r[0])
        if t0 <= t <= t1:
            series.setdefault(g, []).append((t, float(r[2]), float(r[3]), float(r[5])))
    joules, temps, limits, peak = 0.0, [], set(), float("nan")
    for g, s in series.items():
        s.sort()
        joules += sum((b[0] - a[0]) * (a[1] + b[1]) / 2.0 for a, b in zip(s, s[1:]))
        temps += [x[2] for x in s]; limits |= {x[3] for x in s}
    peak = max(temps) if temps else float("nan")
    req = list(csv.DictReader(open(d / "requests.csv")))
    ms = [float(r["latency_ms"]) for r in req if r["ok"] == "1"]
    served, lost = len(ms), sum(1 for r in req if r["ok"] != "1")
    g = {PRIMARY: served / (joules / 1000.0) if joules > 0 else float("nan"), "energy, GPU (J)": joules, "energy per served request (J)": joules / served if served else float("nan"),
         "power, GPU mean (W)": joules / max(1e-9, t1 - t0), "requests served": float(served), "requests not served": float(lost),
         "response time, mean (ms)": sum(ms) / served if served else float("nan"),
         "response time, 95th percentile (ms)": pct(ms, 0.95), "response time, 99th percentile (ms)": pct(ms, 0.99),
         "temperature, peak (C)": peak, "temperature, mean (C)": sum(temps) / len(temps) if temps else float("nan"),
         "energy, CPU package (J)": float("nan"), "energy, whole machine at the wall (J)": float("nan"), WALL: float("nan")}
    if (d / "wall.csv").exists():
        w = [(float(r["epoch_s"]), float(r["watts"])) for r in csv.DictReader(open(d / "wall.csv")) if r["watts"]]
        w = [x for x in w if t0 <= x[0] <= t1]
        # a gap in the plug's readings longer than 5 s leaves the arm without a wall number, never an interpolated one
        if len(w) > 1 and w[0][0] - t0 < 5 and t1 - w[-1][0] < 5 and all(b[0] - a[0] < 5 for a, b in zip(w, w[1:])):
            wj = sum((b[0] - a[0]) * (a[1] + b[1]) / 2.0 for a, b in zip(w, w[1:]))
            g["energy, whole machine at the wall (J)"] = wj
            g[WALL] = served / (wj / 1000.0) if wj > 0 else float("nan")
    if (d / "rapl_start.txt").exists() and (d / "rapl_end.txt").exists():
        a = [int(x) for x in (d / "rapl_start.txt").read_text().split()]; b = [int(x) for x in (d / "rapl_end.txt").read_text().split()]
        rng = [int(x) for x in (d / "rapl_range.txt").read_text().split()] if (d / "rapl_range.txt").exists() else [0] * len(a)
        if a and len(a) == len(b):
            g["energy, CPU package (J)"] = sum(((y - x) % r if r else (y - x)) for x, y, r in zip(a, b, rng)) / 1e6
    writes = would = 0
    if (d / "audit.jsonl").exists():
        for line in open(d / "audit.jsonl"):
            rec = json.loads(line)
            writes += "write" in rec; would += "would_write" in rec
    restored = (d / "limit_end.txt").read_text().split() == (d / "limit_start.txt").read_text().split() \
        if (d / "limit_end.txt").exists() else False
    return g, {"limits_seen": sorted(limits), "writes": writes, "would_write": would, "restored": restored, "samples": sum(map(len, series.values()))}


def verdict(k, mean, half, n):
    if n < 2 or math.isnan(half):
        return "not proven (too few repetitions)"
    if abs(mean) < 1e-12 and half < 1e-12:
        return "equal"
    better = (mean < 0) == (k in LOWER)
    proven = mean - half > 0 or mean + half < 0
    return ("better" if better else "worse") + (", proven" if proven else ", not proven")


def main(root):
    root = Path(root)
    receipt = json.loads((root / "receipt.json").read_text()) if (root / "receipt.json").exists() else {}
    gpus = [int(x) for x in str(receipt.get("gpus", "0")).split(",")]
    if not receipt and sorted(root.glob("rep-*/receipt.json")):
        receipt = json.loads(sorted(root.glob("rep-*/receipt.json"))[0].read_text())
        gpus = [int(x) for x in str(receipt.get("gpus", "0")).split(",")]
    start0 = (root / "snapshot.txt").read_text().split() if (root / "snapshot.txt").exists() else []
    start = start0
    runs, checks, problems = {}, {}, []
    for d in sorted(root.glob("rep-*/*")):
        if not (d / "requests.csv").exists():
            continue
        rep, a = d.parent.name.split("-", 1)[1], d.name
        start = (d.parent / "snapshot.txt").read_text().split() if (d.parent / "snapshot.txt").exists() else start0
        g, c = arm(d, gpus)
        runs.setdefault(a, {})[rep] = g; checks.setdefault(a, {})[rep] = c
        lim = [f"{x:.2f}" for x in c["limits_seen"]]
        if a in ("native", "watch") and start and any(all(abs(x - float(s)) >= 1.0 for s in start) for x in c["limits_seen"]):
            problems.append(f"{a} rep {rep}: power limit {lim} differs from the start limit {start}")
        if a == "watch" and c["writes"]:
            problems.append(f"watch rep {rep}: {c['writes']} power-limit writes executed (the control arm must write nothing)")
        if a == "native" and c["writes"] + c["would_write"]:
            problems.append(f"native rep {rep}: Omni records present")
        if not c["restored"]:
            problems.append(f"{a} rep {rep}: the limit at the end differs from the start (kill switch did not restore)")
    fz = [json.loads((root / f).read_text()) for f in ("FREEZE.json", "FREEZE_END.json") if (root / f).exists()]
    fz += [json.loads(f.read_text()) for f in sorted(root.glob("rep-*/FREEZE*.json"))]
    if fz and any(x["files"] != fz[0]["files"] for x in fz):
        problems.append("Omni changed during the run: the frozen file hashes differ between the start, the end, or the machines")
    if fz and fz[0].get("phase") == "confirm" and fz[0].get("dirty"):
        problems.append("confirmation run on uncommitted Omni code")
    out = {"freeze": fz[0] if fz else None, "receipt": receipt, "start_limit_w": start, "checks": checks, "problems": problems, "means": {}, "paired": {}}
    names = {"native": "Native", "watch": "Omni watches only", "omni": "Omni governs"}
    cols = [a for a in ("native", "watch", "omni") if a in runs]
    L = ["# GPU bench: native vs Omni-Compass, metered by the device", ""]
    if receipt:
        L += [f"GPU {receipt.get('gpu_name', '?')}, driver {receipt.get('driver', '?')}, persistence mode "
              f"{receipt.get('persistence', '?')}, start power limit {', '.join(start)} W, workload {receipt.get('workload', '?')}.",
              f"{receipt.get('reps', '?')} repetitions, order rotated, {receipt.get('duration_s', '?')} s per arm plus "
              f"{receipt.get('drain_s', '?')} s drain, {receipt.get('cooldown_s', '?')} s idle before each arm.", ""]
    if fz:
        L += [f"Phase: **{fz[0].get('phase')}**. Omni frozen at commit {fz[0].get('commit', '?')[:12]}"
              f"{' (uncommitted changes present)' if fz[0].get('dirty') else ''}; file hashes in FREEZE.json, rechecked at the end.", ""]
    if problems:
        L += ["## INVALID RUN", ""] + [f"- {p}" for p in problems] + [""]
    for a in cols:
        out["means"][a] = {k: _mean([g[k] for g in runs[a].values()]) for k in KEYS}
    L += ["## Every column, mean over repetitions", "", "| Gauge | " + " | ".join(names[a] for a in cols) + " |",
          "|---|" + "---:|" * len(cols)]
    L += [f"| {k} | " + " | ".join(_f(out["means"][a][k]) for a in cols) + " |" for k in KEYS if not all(math.isnan(out["means"][a][k]) for a in cols)]
    L.append("")
    for a in ("omni", "watch"):
        if a not in runs or "native" not in runs:
            continue
        reps = sorted(set(runs[a]) & set(runs["native"]), key=int)
        out["paired"][a] = {}
        L += [f"## {names[a]} against native, {len(reps)} paired repetitions", "",
              f"| Gauge | Native | {names[a]} | Change | 95% interval of the difference | Verdict |", "|---|---:|---:|---:|---:|---|"]
        for k in KEYS:
            dd = [runs[a][r][k] - runs["native"][r][k] for r in reps if not math.isnan(runs[a][r][k]) and not math.isnan(runs["native"][r][k])]
            if not dd:
                continue
            n = len(dd); m = sum(dd) / n
            sd = math.sqrt(sum((x - m) ** 2 for x in dd) / (n - 1)) if n > 1 else float("nan")
            half = T95.get(n - 1, 1.96) * sd / math.sqrt(n) if n > 1 else float("nan")
            nb = _mean([runs["native"][r][k] for r in reps]); ob = nb + m
            v = verdict(k, m, half, n)
            ch = f"{(ob - nb) / abs(nb) * 100:+.1f}%" if abs(nb) > 1e-12 else f"{m:+.3g}"
            out["paired"][a][k] = {"native": nb, a: ob, "diff": m, "ci95": [m - half, m + half], "verdict": v}
            L.append(f"| {'**' + k + ' (primary)**' if k == PRIMARY else k} | {_f(nb)} | {_f(ob)} | {ch} | {m - half:+.4g} to {m + half:+.4g} | {v} |")
        L.append("")
    wr = {a: sum(c["writes"] for c in checks.get(a, {}).values()) for a in cols}
    # the preregistered verdict (docs/GPU_PREREGISTRATION.md): primary outcome with the two service guardrails
    po = out["paired"].get("omni", {})
    if PRIMARY in po:
        prim = po[PRIMARY]["verdict"]
        sv, p95 = po.get("requests served"), po.get("response time, 95th percentile (ms)")
        g_served = sv is not None and sv["ci95"][0] >= -0.01 * abs(sv["native"])
        g_p95 = p95 is not None and p95["ci95"][1] <= 0.10 * abs(p95["native"])
        if prim == "better, proven":
            head = "better, proven" if g_served and g_p95 else "better on energy, fails the service guardrail"
        else:
            head = prim
        wv = out["paired"].get("watch", {}).get(PRIMARY, {}).get("verdict")
        out["headline"] = {"primary": prim, "guardrail_served": g_served, "guardrail_p95": g_p95, "verdict": head,
                           "watch_primary": wv, "wall": po.get(WALL, {}).get("verdict"), "valid": not problems}
        c = po[PRIMARY]
        L += ["## Verdict on the preregistered question", "",
              f"Work per energy under Omni against native: {_f(c['native'])} -> {_f(c['omni'])} served requests per kJ, "
              f"difference {c['diff']:+.4g} (95% interval {c['ci95'][0]:+.4g} to {c['ci95'][1]:+.4g}).",
              f"Guardrails: requests served {'held' if g_served else 'FAILED'} (not below -1%), "
              f"95th-percentile response time {'held' if g_p95 else 'FAILED'} (not above +10%).",
              f"Watch against native on the same outcome: {wv or 'n/a'}.",
              *([f"Whole machine at the wall (smart plug Omni never reads): {po[WALL]['verdict']}, "
                 f"{_f(po[WALL]['native'])} -> {_f(po[WALL]['omni'])} served requests per kJ."] if WALL in po else []),
              f"**Verdict: {head}{'' if not problems else ' (the run is INVALID; see above)'}.**", ""]
    L += ["## The control", "", f"- Power-limit writes executed: " + ", ".join(f"{names[a]} {wr[a]}" for a in cols) + ".",
          "- Every arm ended at the start limit." if not any("restore" in p for p in problems) else "- An arm did NOT end at the start limit.",
          "- Energy is the device's own power.draw integrated over time; no number here is modelled.", ""]
    (root / "GPU_REPS.json").write_text(json.dumps(out, indent=1)); (root / "GPU_REPS.md").write_text("\n".join(L))
    print("\n".join(L))
    return 2 if problems else 0


def _mean(xs):
    xs = [x for x in xs if not math.isnan(x)]
    return sum(xs) / len(xs) if xs else float("nan")


def _f(x):
    return "n/a" if math.isnan(x) else f"{x:.4g}"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
