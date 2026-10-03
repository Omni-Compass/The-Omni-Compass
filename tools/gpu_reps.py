# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The GPU bench table (scripts/gpu_paired.sh): native / watch (Omni runs, writes nothing) / omni (Omni writes power limits).

Every energy number comes from the device: joules = the time integral of nvidia-smi power.draw over the measured window
(trapezoid rule on its own sample timestamps), summed over the measured GPUs; the CPU package joules come from RAPL
energy counters when the machine has them. Nothing here is a model.

Per repetition, per arm: energy, joules per served request, mean power, peak and mean temperature, served and not
served requests, response time (mean, 95th, 99th percentile), power-limit writes. Across repetitions: for watch and omni
against native, the paired mean difference with a t-based 95% interval. A difference is proven when that interval
excludes zero; otherwise the table says not proven.

Three contrasts, each paired by repetition: observation = watch − native (does Omni's presence alone move the plant),
authority = omni − watch (what granting Omni the write adds), total = omni − native (the preregistered comparison).
Three receipts, kept apart: A the governor's decisions (audit.jsonl), B its actuator records (requested, return code,
read-back, enforced limit, delay), C the bench's own nvidia-smi samples and the workload's requests. From A and B the
table also reports actuator fidelity, control effort, and how well the engine's six-state projection matches what the
telemetry shows next (the intertwining residual and directional accuracy), defined in docs/GPU_PREREGISTRATION.md.
The result label is chosen by rule (label()), never by hand. A meter that was not fitted prints UNAVAILABLE.

The run is INVALID (exit 2) when: a native or watch arm saw a power limit (or enforced limit) other than the one read at
start, the watch arm executed a write, an arm ended with a limit that differs from the start (the kill switch did not
restore), a governor exited nonzero (a refused write, a refused start), a write was refused, Omni's frozen files
changed, a confirmation ran on uncommitted code, or smoke and confirmation repetitions were mixed.
Usage: python tools/gpu_reps.py RUN_DIR   (RUN_DIR holds rep-<n>/<arm>/)  ->  RUN_DIR/GPU_REPS.md, RUN_DIR/GPU_REPS.json"""
from __future__ import annotations

import csv, datetime as dt, json, math, statistics, sys
from pathlib import Path

U_AUTHORITY = 25.0          # omnicompass/core.py: the U-channel command's bound (saturation)
DEADBAND = 0.01             # directional accuracy: a movement under this (state units) is not a direction
W_INT = {"E": 1.0, "U": 1.0, "I_U": 1.0, "S": 1.0, "B": 1.0}   # the residual's weights, declared before any trial
MARGIN_SERVED, MARGIN_P95, MARGIN_LOST = 0.01, 0.10, 0.01      # guardrails (docs/GPU_PREREGISTRATION.md)
SMI_DEFAULT = "timestamp,index,power.draw,temperature.gpu,utilization.gpu,power.limit,clocks.sm"

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201,
       12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}
LOWER = {"energy, whole machine at the wall (J)", "energy, GPU (J)", "energy per served request (J)", "power, GPU mean (W)", "temperature, peak (C)",
         "temperature, mean (C)", "requests not served", "response time, mean (ms)", "response time, 95th percentile (ms)",
         "response time, 99th percentile (ms)", "energy, CPU package (J)", "energy, rest of the machine (J)",
         "energy, DRAM (J)", "energy, platform psys (J)", "energy, GPU device counter (J)"}
PRIMARY = "work per energy (served requests per kJ)"
WALL = "work per wall energy (served requests per kJ, whole machine)"
KEYS = [PRIMARY, WALL, "energy, whole machine at the wall (J)", "energy, GPU (J)", "energy per served request (J)", "power, GPU mean (W)", "requests served", "requests not served",
        "response time, mean (ms)", "response time, 95th percentile (ms)", "response time, 99th percentile (ms)",
        "temperature, peak (C)", "temperature, mean (C)", "energy, CPU package (J)", "energy, DRAM (J)", "energy, platform psys (J)",
        "energy, rest of the machine (J)", "energy, GPU device counter (J)", "power-capped share of samples"]
PHYSICAL = {"energy, whole machine at the wall (J)", "energy, CPU package (J)", "energy, rest of the machine (J)", WALL,
            "energy, DRAM (J)", "energy, platform psys (J)", "energy, GPU device counter (J)"}


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
    fields = ((d / "smi_fields.txt").read_text().strip() if (d / "smi_fields.txt").exists() else SMI_DEFAULT).split(",")
    ix = {f: i for i, f in enumerate(fields)}
    ie = ix.get("enforced.power.limit"); ir = ix.get("clocks_event_reasons.active", ix.get("clocks_throttle_reasons.active"))
    series, enforced, capped, nre = {}, set(), 0, 0
    for r in csv.reader(open(d / "smi.csv")):
        if len(r) < len(fields) or not r[1].strip().isdigit():
            continue
        g = int(r[1])
        if g not in gpus:
            continue
        t = smi_time(r[0])
        if t0 <= t <= t1:
            series.setdefault(g, []).append((t, float(r[2]), float(r[3]), float(r[5])))
            if ie is not None:
                enforced.add(float(r[ie]))
            if ir is not None:
                try:
                    capped += bool(int(r[ir].strip(), 16) & 0x4); nre += 1   # bit 2: software power cap
                except ValueError:
                    pass
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
         "energy, CPU package (J)": float("nan"), "energy, whole machine at the wall (J)": float("nan"), WALL: float("nan"),
         "energy, rest of the machine (J)": float("nan"), "energy, DRAM (J)": float("nan"), "energy, platform psys (J)": float("nan"),
         "power-capped share of samples": capped / nre if nre else float("nan")}
    if (d / "wall.csv").exists():
        w = [(float(r["epoch_s"]), float(r["watts"])) for r in csv.DictReader(open(d / "wall.csv")) if r["watts"]]
        w = [x for x in w if t0 <= x[0] <= t1]
        # a gap in the plug's readings longer than 5 s leaves the arm without a wall number, never an interpolated one
        if len(w) > 1 and w[0][0] - t0 < 5 and t1 - w[-1][0] < 5 and all(b[0] - a[0] < 5 for a, b in zip(w, w[1:])):
            wj = sum((b[0] - a[0]) * (a[1] + b[1]) / 2.0 for a, b in zip(w, w[1:]))
            g["energy, whole machine at the wall (J)"] = wj
            g[WALL] = served / (wj / 1000.0) if wj > 0 else float("nan")
    g.update(rapl_energy(d))
    g["energy, GPU device counter (J)"] = float("nan")
    dv0, dv1 = _kv(d / "device_start.txt"), _kv(d / "device_end.txt")
    try:
        g["energy, GPU device counter (J)"] = (float(dv1["energy_mj"]) - float(dv0["energy_mj"])) / 1000.0
    except (KeyError, ValueError):
        pass
    # the rest of the machine only when the wall, the GPU and the CPU package measured this arm: wall − GPU − package
    # (− DRAM where measured), never modelled
    if not math.isnan(g["energy, whole machine at the wall (J)"]) and not math.isnan(g["energy, CPU package (J)"]):
        dram = g["energy, DRAM (J)"]
        g["energy, rest of the machine (J)"] = (g["energy, whole machine at the wall (J)"] - joules - g["energy, CPU package (J)"]
                                              - (0.0 if math.isnan(dram) else dram))
    writes = would = 0
    for af in sorted(d.glob("audit*.jsonl")):          # audit.jsonl, or audit-<card>.jsonl with one governor per card
        for line in open(af):
            rec = json.loads(line)
            writes += "write" in rec; would += "would_write" in rec
            # the two-wire engine's clock wire counts too (its reset at the end is the restore, not a write)
            writes += "clock_write" in rec and rec.get("why") != "restore"; would += "would_clock_write" in rec
    restored = (d / "limit_end.txt").read_text().split() == (d / "limit_start.txt").read_text().split() \
        if (d / "limit_end.txt").exists() else False
    gx = (d / "governor_exit.txt").read_text().strip() if (d / "governor_exit.txt").exists() else None
    return g, {"limits_seen": sorted(limits), "enforced_seen": sorted(enforced), "writes": writes, "would_write": would,
               "restored": restored, "governor_exit": gx, "samples": sum(map(len, series.values())), "health": health(d),
               **receipts(d)}


def _kv(f):
    return dict(x.split(" ", 1) for x in f.read_text().splitlines() if " " in x) if f.exists() else {}


def health(d):
    """Card health over the arm (bench only): change in uncorrected and corrected ECC errors, pages pending retirement."""
    a, b = _kv(d / "device_start.txt"), _kv(d / "device_end.txt"); out = {}
    for k in ("ecc.errors.uncorrected.volatile.total", "ecc.errors.corrected.volatile.total", "retired_pages.pending"):
        try:
            out[k] = float(b[k]) - float(a[k]) if k != "retired_pages.pending" else b[k]
        except (KeyError, ValueError):
            out[k] = None
    return out


def rapl_delta(e0, e1, rng):
    """A wrapping microjoule counter's increase: modular when the range is known; unknown (None) if it went backwards
    without one."""
    if e1 >= e0:
        return e1 - e0
    return e1 - e0 + rng if rng > 0 else None


def rapl_energy(d):
    """CPU package and DRAM joules (summed over sockets, separately) and platform (psys) joules from rapl_start.tsv /
    rapl_end.tsv; NaN (printed UNAVAILABLE) where the counters were missing or unreadable. package + dram is the CPU
    side; psys is a wider, vendor-defined scope and is never added to them."""
    out = {"energy, CPU package (J)": float("nan"), "energy, DRAM (J)": float("nan"), "energy, platform psys (J)": float("nan")}
    f0, f1 = d / "rapl_start.tsv", d / "rapl_end.tsv"
    if f0.exists() and f1.exists():
        rd = lambda f: {x.split()[0]: x.split() for x in f.read_text().splitlines() if len(x.split()) == 4}
        a, b = rd(f0), rd(f1)
        sums = {}
        for dom, (_, name, e0, rng) in a.items():
            if dom not in b:
                continue
            kind = "package" if name.startswith("package") else name
            dl = rapl_delta(int(e0), int(b[dom][2]), int(rng))
            sums.setdefault(kind, []).append(dl)
        for kind, key in (("package", "energy, CPU package (J)"), ("dram", "energy, DRAM (J)"), ("psys", "energy, platform psys (J)")):
            if sums.get(kind) and None not in sums[kind]:
                out[key] = sum(sums[kind]) / 1e6
    elif (d / "rapl_start.txt").exists() and (d / "rapl_end.txt").exists():      # runs recorded before the named format
        a = [int(x) for x in (d / "rapl_start.txt").read_text().split()]; b = [int(x) for x in (d / "rapl_end.txt").read_text().split()]
        rng = [int(x) for x in (d / "rapl_range.txt").read_text().split()] if (d / "rapl_range.txt").exists() else [0] * len(a)
        dl = [rapl_delta(x, y, r) for x, y, r in zip(a, b, rng)]
        if a and len(a) == len(b) and None not in dl:
            out["energy, CPU package (J)"] = sum(dl) / 1e6
    return out


def credit(root, runs_dirs):
    """Per write, credited against the same moments of the same seeded request stream in the native arm (and the watch
    arm): GPU joules and requests finished in the interval from this write to the next, omni minus native. The
    intervals tile the arm, so the credits add up to the whole difference they cover. Also who decided each write."""
    rows = []
    for rep, arms in runs_dirs.items():
        if "omni" not in arms or "native" not in arms:
            continue
        do = arms["omni"]
        if not (do / "audit.jsonl").exists():
            continue
        recs = [json.loads(x) for x in open(do / "audit.jsonl") if x.strip()]
        t_start = float((do / "window_start.txt").read_text().split()[0]); t_end = float((do / "window_end.txt").read_text().split()[0])
        last_dec, writes = {}, []
        for r in recs:
            if "decision" in r:
                for gk, v in r["decision"].items():
                    if "decided_by" in v:
                        last_dec[gk] = v["decided_by"]
            if "actuator" in r and r["actuator"].get("rc") == 0:
                a = r["actuator"]
                writes.append((a["t_requested"] - t_start, a["requested_w"], last_dec.get(str(a["gpu"]), "?")))
        if not writes:
            continue
        L = t_end - t_start
        edges = [w[0] for w in writes] + [L]
        series = {a: _series(arms[a], t0=float((arms[a] / "window_start.txt").read_text().split()[0])) for a in ("omni", "native", "watch") if a in arms}
        done = {a: _done(arms[a]) for a in series}
        for (t, w, who), t_next in zip(writes, edges[1:]):
            if t_next <= t:
                continue
            row = {"rep": rep, "t_s": round(t, 1), "limit_w": w, "decided_by": who, "interval_s": round(t_next - t, 1)}
            for a in ("native", "watch"):
                if a in series:
                    row[f"dJ_vs_{a}"] = _energy(series["omni"], t, t_next) - _energy(series[a], t, t_next)
                    row[f"dserved_vs_{a}"] = _count(done["omni"], t, t_next) - _count(done[a], t, t_next)
            rows.append(row)
    by = {}
    for r in rows:
        b = by.setdefault(r["decided_by"], {"writes": 0, "dJ_vs_native": 0.0, "dserved_vs_native": 0, "seconds": 0.0})
        b["writes"] += 1; b["dJ_vs_native"] += r.get("dJ_vs_native", 0.0); b["dserved_vs_native"] += r.get("dserved_vs_native", 0)
        b["seconds"] += r["interval_s"]
    return rows, by


def _series(d, t0):
    fields = ((d / "smi_fields.txt").read_text().strip() if (d / "smi_fields.txt").exists() else SMI_DEFAULT).split(",")
    s = []
    for r in csv.reader(open(d / "smi.csv")):
        if len(r) >= len(fields) and r[1].strip().isdigit():
            try:
                s.append((smi_time(r[0]) - t0, float(r[2])))
            except ValueError:
                pass
    return sorted(s)


def _energy(s, a, b):
    pts = [x for x in s if a <= x[0] <= b]
    return sum((q[0] - p[0]) * (p[1] + q[1]) / 2.0 for p, q in zip(pts, pts[1:]))


def _done(d):
    """Finish times of served requests on the arm's own window clock (the workload's t0_epoch against window_start)."""
    off = 0.0
    if (d / "summary.json").exists():
        t0e = json.loads((d / "summary.json").read_text()).get("t0_epoch")
        if t0e:
            off = t0e - float((d / "window_start.txt").read_text().split()[0])
    return [float(r["done_s"]) + off for r in csv.DictReader(open(d / "requests.csv")) if r["ok"] == "1" and r["done_s"]]


def _count(ts, a, b):
    return sum(1 for t in ts if a <= t < b)


def receipts(d):
    """Receipts A and B from the governor's audit: actuator fidelity, control effort, representation fidelity."""
    if not (d / "audit.jsonl").exists():
        return {}
    recs = [json.loads(x) for x in open(d / "audit.jsonl") if x.strip()]
    snap = next((r["snapshot"] for r in recs if "snapshot" in r), {})
    start = {g: v.get("limit_w") for g, v in snap.items()}
    # B: actuator
    act = [r["actuator"] for r in recs if "actuator" in r]
    late = {(x["gpu"], x["requested_w"]): x for x in (r["actuator_realized"] for r in recs if "actuator_realized" in r)}
    r_act, delay, realized, over = [], [], {}, 0
    for a in act:
        if a.get("rc") != 0:
            continue
        rb = a.get("readback_w"); lt = late.get((a["gpu"], a["requested_w"]))
        if not a.get("realized") and lt:
            rb = lt["readback_w"]; delay.append(lt["delay_s"])
        elif a.get("realized"):
            delay.append(a["delay_s"])
        if rb is not None:
            r_act.append(rb - a["requested_w"]); realized.setdefault(str(a["gpu"]), []).append(rb)
        over += bool(a.get("override"))
    tv, rev = 0.0, 0
    for g, seq in realized.items():
        seq = ([start[g]] if start.get(g) is not None else []) + seq
        steps = [b - a for a, b in zip(seq, seq[1:]) if abs(b - a) >= 1.0]
        tv += sum(abs(x) for x in steps); rev += sum(1 for a, b in zip(steps, steps[1:]) if (a > 0) != (b > 0))
    rest = next((r for r in reversed(recs) if "restored" in r), None)
    # A: governor decisions and control effort
    dec = [(r["time"], g, v) for r in recs if "decision" in r for g, v in r["decision"].items() if "telemetry" in v]
    u = [abs(v.get("u_push", 0.0)) for _, _, v in dec if "u_push" in v]
    times = sorted({t for t, _, _ in dec}); dts = [b - a for a, b in zip(times, times[1:])]
    dt0 = statistics.median(dts) if dts else 0.0
    J_u = sum(abs(v.get("u_push", 0.0)) * dt0 for _, _, v in dec)
    bounds = [v.get("shield_bound") for _, _, v in dec]
    # representation: the engine's projection against what the telemetry shows at the next decision
    by = {}
    for t, g, v in dec:
        by.setdefault(g, []).append(v)
    res2, n_res, dirs, bins = 0.0, 0, {k: [0, 0] for k in W_INT}, {"0.01-0.03": [0, 0], "0.03-0.1": [0, 0], ">=0.1": [0, 0]}
    for g, vs in by.items():
        for a, b in zip(vs, vs[1:]):
            if "state_measured" not in a or "state_measured" not in b:
                continue
            res2 += sum(W_INT[k] * (b["state_measured"][k] - a["state_projected_next"][k]) ** 2 for k in W_INT); n_res += 1
            for k in W_INT:
                pred = a["state_projected_next"][k] - a["state_observed"][k]
                real = b["state_measured"][k] - a["state_measured"][k]
                if abs(pred) >= DEADBAND and abs(real) >= DEADBAND:
                    hit = (pred > 0) == (real > 0); dirs[k][0] += hit; dirs[k][1] += 1
                    key = "0.01-0.03" if abs(pred) < 0.03 else "0.03-0.1" if abs(pred) < 0.1 else ">=0.1"
                    bins[key][0] += hit; bins[key][1] += 1
    hits, valid = sum(x[0] for x in dirs.values()), sum(x[1] for x in dirs.values())
    return {"actuator": {"writes_ok": sum(1 for a in act if a.get("rc") == 0), "writes_refused": sum(1 for a in act if a.get("rc") != 0),
                         "r_act_mean_abs_w": statistics.mean(abs(x) for x in r_act) if r_act else None,
                         "r_act_max_abs_w": max((abs(x) for x in r_act), default=None),
                         "delay_median_s": statistics.median(delay) if delay else None, "delay_max_s": max(delay, default=None),
                         "enforced_under_requested": over, "total_variation_w": tv, "reversals": rev,
                         "restored_ok": rest.get("ok") if rest else None},
            "governor": {"decisions": len(dec), "J_u": J_u, "u_mean_abs": statistics.mean(u) if u else None,
                         "u_max_abs": max(u, default=None), "saturations": sum(1 for x in u if x >= U_AUTHORITY - 1e-9),
                         "shield_interventions": sum(1 for b in bounds if b not in ("engine", "start_ceiling")),
                         "bounds": {b: bounds.count(b) for b in sorted(set(filter(None, bounds)))},
                         "holds": sum(1 for r in recs if "decision" in r for v in r["decision"].values() if "hold" in v)},
            "representation": {"pairs": n_res, "R_int": math.sqrt(res2 / n_res) if n_res else None,
                               "directional_accuracy": hits / valid if valid else None, "directional_valid": valid,
                               "by_state": {k: (x[0] / x[1] if x[1] else None, x[1]) for k, x in dirs.items()},
                               "by_predicted_size": {k: (x[0] / x[1] if x[1] else None, x[1]) for k, x in bins.items()}}}


def label(prim, g_served, g_p95, g_lost, valid, observation=None):
    """The result label, by rule (docs/GPU_PREREGISTRATION.md), from the primary verdict, the three guardrails, and the
    observation contrast: if Omni watching (writing nothing) already differs from native on the primary outcome, proven
    either way, the effect cannot be credited to Omni's authority and no omni result is published."""
    if not valid:
        return "INVALID"
    if observation in ("better, proven", "worse, proven"):
        return "NOT ATTRIBUTABLE: WATCH DIFFERS FROM NATIVE"
    ok = g_served and g_p95 and g_lost
    if prim == "better, proven":
        return "SUPERIOR WITHIN GUARDRAILS" if ok else "ENERGY IMPROVEMENT WITH SERVICE TRADEOFF"
    if prim == "worse, proven":
        return "WORSE"
    return "NONINFERIOR / INCONCLUSIVE" if ok else "NOT ESTABLISHED"


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
    runs, checks, problems, dirs = {}, {}, [], {}
    for d in sorted(root.glob("rep-*/*")):
        if not (d / "requests.csv").exists():
            continue
        rep, a = d.parent.name.split("-", 1)[1], d.name
        start = (d.parent / "snapshot.txt").read_text().split() if (d.parent / "snapshot.txt").exists() else start0
        # a repetition pooled from another card or machine carries its own receipt: read that card, not the first one's
        rg = json.loads((d.parent / "receipt.json").read_text()).get("gpus") if (d.parent / "receipt.json").exists() else None
        g, c = arm(d, [int(x) for x in str(rg).split(",")] if rg is not None else gpus); dirs.setdefault(rep, {})[a] = d
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
        rc = json.loads((d.parent / "receipt.json").read_text()) if (d.parent / "receipt.json").exists() else receipt
        enf0 = str(rc.get("power_limit_enforced_w", "unsupported"))
        if a in ("native", "watch") and c["enforced_seen"] and enf0 not in ("", "unsupported") \
                and any(all(abs(x - float(e)) >= 1.0 for e in enf0.split()) for x in c["enforced_seen"]):   # one value per card
            problems.append(f"{a} rep {rep}: enforced power limit {c['enforced_seen']} differs from the snapshot {enf0}")
        if a in ("watch", "omni") and c["governor_exit"] not in (None, "0"):
            problems.append(f"{a} rep {rep}: the governor exited {c['governor_exit']} (a refused write or a refused start)")
        if c.get("actuator", {}).get("writes_refused"):
            problems.append(f"{a} rep {rep}: {c['actuator']['writes_refused']} power-limit writes refused by the device")
    fz = [json.loads((root / f).read_text()) for f in ("FREEZE.json", "FREEZE_END.json") if (root / f).exists()]
    fz += [json.loads(f.read_text()) for f in sorted(root.glob("rep-*/FREEZE*.json"))]
    if fz and any(x["files"] != fz[0]["files"] for x in fz):
        problems.append("Omni changed during the run: the frozen file hashes differ between the start, the end, or the machines")
    if fz and fz[0].get("phase") == "confirm" and fz[0].get("dirty"):
        problems.append("confirmation run on uncommitted Omni code")
    if len({x.get("phase") for x in fz}) > 1:
        problems.append("smoke and confirmation repetitions mixed: smoke data never enter the confirmation")
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
    L += [f"| {k} | " + " | ".join("UNAVAILABLE" if k in PHYSICAL and math.isnan(out["means"][a][k]) else _f(out["means"][a][k]) for a in cols) + " |"
          for k in KEYS if k in PHYSICAL or not all(math.isnan(out["means"][a][k]) for a in cols)]
    L.append("")
    # three contrasts: total (the preregistered one), observation, authority
    for a, b, key, what in (("omni", "native", "omni", "Total: Omni governs against native"),
                            ("watch", "native", "watch", "Observation: Omni watches only against native"),
                            ("omni", "watch", "omni_vs_watch", "Authority: Omni governs against Omni watching")):
        if a not in runs or b not in runs:
            continue
        reps = sorted(set(runs[a]) & set(runs[b]), key=int)
        out["paired"][key] = {}
        L += [f"## {what}, {len(reps)} paired repetitions", "",
              f"| Gauge | {names[b]} | {names[a]} | Change | 95% interval of the difference | Verdict |", "|---|---:|---:|---:|---:|---|"]
        for k in KEYS:
            dd = [runs[a][r][k] - runs[b][r][k] for r in reps if not math.isnan(runs[a][r][k]) and not math.isnan(runs[b][r][k])]
            if not dd:
                if k in PHYSICAL:
                    L.append(f"| {k} | UNAVAILABLE | UNAVAILABLE | | | no meter |")
                continue
            n = len(dd); m = sum(dd) / n
            sd = math.sqrt(sum((x - m) ** 2 for x in dd) / (n - 1)) if n > 1 else float("nan")
            half = T95.get(n - 1, 1.96) * sd / math.sqrt(n) if n > 1 else float("nan")
            nb = _mean([runs[b][r][k] for r in reps]); ob = nb + m
            v = verdict(k, m, half, n)
            ch = f"{(ob - nb) / abs(nb) * 100:+.1f}%" if abs(nb) > 1e-12 else f"{m:+.3g}"
            out["paired"][key][k] = {"native" if b == "native" else b: nb, a: ob, "base": nb, "diff": m, "ci95": [m - half, m + half], "verdict": v}
            L.append(f"| {'**' + k + ' (primary)**' if k == PRIMARY else k} | {_f(nb)} | {_f(ob)} | {ch} | {m - half:+.4g} to {m + half:+.4g} | {v} |")
        L.append("")
    wr = {a: sum(c["writes"] for c in checks.get(a, {}).values()) for a in cols}
    # the preregistered verdict (docs/GPU_PREREGISTRATION.md): primary outcome with the two service guardrails
    po = out["paired"].get("omni", {})
    if PRIMARY in po:
        prim = po[PRIMARY]["verdict"]
        sv, p95 = po.get("requests served"), po.get("response time, 95th percentile (ms)")
        lost = po.get("requests not served")
        g_served = sv is not None and sv["ci95"][0] >= -MARGIN_SERVED * abs(sv["native"])
        g_p95 = p95 is not None and p95["ci95"][1] <= MARGIN_P95 * abs(p95["native"])
        g_lost = lost is None or sv is None or lost["ci95"][1] <= MARGIN_LOST * abs(sv["native"])
        wv = out["paired"].get("watch", {}).get(PRIMARY, {}).get("verdict")
        head = label(prim, g_served, g_p95, g_lost, not problems, wv)
        av = out["paired"].get("omni_vs_watch", {}).get(PRIMARY, {}).get("verdict")
        out["headline"] = {"primary": prim, "guardrail_served": g_served, "guardrail_p95": g_p95, "guardrail_not_served": g_lost,
                           "verdict": head, "watch_primary": wv, "authority_primary": av,
                           "wall": po.get(WALL, {}).get("verdict"), "valid": not problems}
        c = po[PRIMARY]
        L += ["## Verdict on the preregistered question", "",
              f"Work per energy under Omni against native: {_f(c['native'])} -> {_f(c['omni'])} served requests per kJ, "
              f"difference {c['diff']:+.4g} (95% interval {c['ci95'][0]:+.4g} to {c['ci95'][1]:+.4g}).",
              f"Guardrails: requests served {'held' if g_served else 'FAILED'} (not below -1%), "
              f"95th-percentile response time {'held' if g_p95 else 'FAILED'} (not above +10%), "
              f"requests not served {'held' if g_lost else 'FAILED'} (not above +1% of native served).",
              f"Observation (watch against native) on the same outcome: {wv or 'n/a'}. "
              f"Authority (omni against watch): {av or 'n/a'}.",
              *([f"Whole machine at the wall (smart plug Omni never reads): {po[WALL]['verdict']}, "
                 f"{_f(po[WALL]['native'])} -> {_f(po[WALL]['omni'])} served requests per kJ."] if WALL in po else []),
              f"**Result, by rule: {head}.**", ""]
    L += receipt_lines(checks)
    crows, cby = credit(root, dirs)
    out["credit"] = {"writes": crows, "by_decider": cby}
    if cby:
        L += ["## Credit per write (against native at the same moments of the same request stream)", "",
              "Each write owns the interval until the next write. Joules and requests finished in it, Omni governing minus native; "
              "the intervals tile the arm, so the credits add up. The decider is the rule that set the written limit "
              "(engine, a floor, the busy gate, a reflex, heat, the speed lock).", "",
              "| Decided by | Writes | Seconds owned | GPU joules vs native | Requests finished vs native |", "|---|---:|---:|---:|---:|"]
        L += [f"| {k} | {v['writes']} | {v['seconds']:.0f} | {v['dJ_vs_native']:+.4g} | {v['dserved_vs_native']:+d} |" for k, v in sorted(cby.items())]
        L.append("")
    L += ["## The control", "", f"- Writes executed (power limit and clock ceiling): " + ", ".join(f"{names[a]} {wr[a]}" for a in cols) + ".",
          "- Every arm ended at the start limit." if not any("restore" in p for p in problems) else "- An arm did NOT end at the start limit.",
          "- Energy is the device's own power.draw integrated over time; no number here is modelled.", ""]
    (root / "GPU_REPS.json").write_text(json.dumps(out, indent=1)); (root / "GPU_REPS.md").write_text("\n".join(L))
    print("\n".join(L))
    return 2 if problems else 0


def receipt_lines(checks):
    """Receipts A and B, per arm and repetition, as the table's own sections."""
    L = []
    rows = [(a, r, c) for a in ("omni", "watch") for r, c in sorted(checks.get(a, {}).items(), key=lambda x: int(x[0])) if c.get("governor")]
    if not rows:
        return L
    fmt = lambda x, n=3: "n/a" if x is None else f"{x:.{n}g}" if isinstance(x, float) else str(x)
    L += ["## Actuator fidelity (receipt B: requested against read back from the device)", "",
          "| Arm | Rep | Writes | Refused | mean abs(read back − requested) W | max W | delay median s | delay max s | enforced under requested | total variation W | reversals | restored |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    L += [f"| {a} | {r} | {c['actuator']['writes_ok']} | {c['actuator']['writes_refused']} | {fmt(c['actuator']['r_act_mean_abs_w'])} | "
          f"{fmt(c['actuator']['r_act_max_abs_w'])} | {fmt(c['actuator']['delay_median_s'])} | {fmt(c['actuator']['delay_max_s'])} | "
          f"{c['actuator']['enforced_under_requested']} | {fmt(c['actuator']['total_variation_w'])} | {c['actuator']['reversals']} | "
          f"{c['actuator']['restored_ok']} |" for a, r, c in rows]
    L += ["", "## Control effort (receipt A)", "",
          "| Arm | Rep | Decisions | J_u = sum abs(u) dt | mean abs(u) | max abs(u) | saturations | shield interventions | holds |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {a} | {r} | {c['governor']['decisions']} | {fmt(c['governor']['J_u'])} | {fmt(c['governor']['u_mean_abs'])} | "
          f"{fmt(c['governor']['u_max_abs'])} | {c['governor']['saturations']} | {c['governor']['shield_interventions']} | "
          f"{c['governor']['holds']} |" for a, r, c in rows]
    L += ["", "## Representation fidelity (the engine's projection against the telemetry at the next decision)", "",
          f"R_int: weighted root-mean-square of h(z next) − F_h(h(z), u) over E, U, I_U, S, B (weights 1). Directional "
          f"accuracy: the share of movements the projection called in the right direction, movements under {DEADBAND} excluded.", "",
          "| Arm | Rep | Pairs | R_int | directional accuracy | valid directions | by predicted size |", "|---|---|---:|---:|---:|---:|---|"]
    L += [f"| {a} | {r} | {c['representation']['pairs']} | {fmt(c['representation']['R_int'])} | "
          f"{fmt(c['representation']['directional_accuracy'])} | {c['representation']['directional_valid']} | "
          + ", ".join(f"{k}: {fmt(v[0])} of {v[1]}" for k, v in c['representation']['by_predicted_size'].items()) + " |"
          for a, r, c in rows]
    return L + [""]


def _mean(xs):
    xs = [x for x in xs if not math.isnan(x)]
    return sum(xs) / len(xs) if xs else float("nan")


def _f(x):
    return "n/a" if math.isnan(x) else f"{x:.4g}"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
