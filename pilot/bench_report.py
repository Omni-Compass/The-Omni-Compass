"""Native vs Omni-Compass benchmark report.

Reads the two captures written by scripts/kind_bench.sh (same cluster wiring, same load schedule; one arm with
Omni-Compass not running, one with Omni-Compass driving) and writes BENCHMARK.md: every gauge side by side,
a per-minute timeline, block-bootstrap significance from pilot/score.py, and the Omni actions taken.

python pilot/bench_report.py --native bench_native/capture.csv --omni bench_omni/capture.csv \
    [--audit bench_omni/audit.jsonl] [--kill bench_omni/kill_switch.txt] [--out BENCHMARK.md]
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pilot.score import load, blocks, compare  # noqa: E402

F = lambda r, k: float(r[k]) if r.get(k, "") not in ("", None) else float("nan")


import os as _os
# scripts/kind_bench.sh: a worker in use draws IDLE_W + DYN_W x utilisation; a parked worker is declared at IDLE_W x PARK_FRAC
PARKED_EXTRA_W = float(_os.environ.get("IDLE_W", 100)) * (1.0 - float(_os.environ.get("PARK_FRAC", 0.25)))


def gauges(rows):
    t = np.array([F(r, "elapsed_seconds") for r in rows])
    dt = np.diff(np.append(t, t[-1] + (t[-1] - t[-2] if len(t) > 1 else 15.0))) / 3600.0
    nodes = np.array([F(r, "nodes_ready") for r in rows]); alloc = np.array([F(r, "alloc_cpu_m") for r in rows]) / 1000
    used = np.array([F(r, "used_cpu_m") for r in rows]) / 1000; pend = np.array([F(r, "pods_pending") for r in rows])
    cur = np.array([F(r, "hpa_current_replicas") for r in rows]); des = np.array([F(r, "hpa_desired_replicas") for r in rows])
    pw = np.array([F(r, "power_w") for r in rows])
    hours = dt.sum(); core_h = (used * dt).sum()
    g = {
        "duration (min)": hours * 60,
        "worker nodes in service, mean": (nodes * dt).sum() / hours,
        "worker nodes in service, min": nodes.min(),
        "worker nodes in service, max": nodes.max(),
        "node-hours": (nodes * dt).sum(),
        "power (W), mean": np.nansum(pw * dt) / hours if not np.isnan(pw).all() else float("nan"),
        "power (W), peak": np.nanmax(pw) if not np.isnan(pw).all() else float("nan"),
        "energy (Wh)": np.nansum(pw * dt) if not np.isnan(pw).all() else float("nan"),
        # the honest row: kind never powers a parked worker off, so it draws its full idle power, not the declared
        # standby (scripts/kind_bench.sh IDLE_W x PARK_FRAC); add the difference for every parked worker-hour
        "energy, parked workers still on at idle power (Wh)": (np.nansum(pw * dt) + PARKED_EXTRA_W * ((nodes.max() - nodes) * dt).sum())
            if not np.isnan(pw).all() else float("nan"),
        "CPU used (cores), mean": core_h / hours,
        "CPU allocatable (cores), mean": (alloc * dt).sum() / hours,
        "utilisation (used / allocatable)": core_h / max((alloc * dt).sum(), 1e-9),
        "energy per core-hour (Wh)": np.nansum(pw * dt) / max(core_h, 1e-9) if not np.isnan(pw).all() else float("nan"),
        "node-hours per core-hour": (nodes * dt).sum() / max(core_h, 1e-9),
        "pending pods, pod-minutes": (pend * dt).sum() * 60,
        "pending pods, peak": pend.max(),
        "HPA replicas, mean": (cur * dt).sum() / hours,
        "HPA replicas, peak": cur.max(),
        "HPA shortfall (desired > current), minutes": ((des > cur) * dt).sum() * 60,
    }
    return {k: float(v) for k, v in g.items()}


def pod_starts(d):
    """Every serving pod created in the measured window, timed from the API server's own record: wait = time its Ready
    condition turned True - its creationTimestamp (1 s resolution); a pod not Ready by the end of the window waits until
    the end. Reads pod_watch.json (kubectl get pods -w --output-watch-events -o json), window_start.txt, window_end.txt."""
    import json as _j, datetime as _dt
    from pathlib import Path as _P
    d = _P(d); f = d / "pod_watch.json"
    if not f.exists():
        return {}
    ts = lambda s: _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc).timestamp()
    t0 = float((d / "window_start.txt").read_text().split()[0]); t1 = float((d / "window_end.txt").read_text().split()[0])
    text = f.read_text(); dec = _j.JSONDecoder(); i = 0; pods = {}
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            ev, i = dec.raw_decode(text, i)
        except ValueError:
            break
        o = ev.get("object", ev); m = o.get("metadata", {}); uid = m.get("uid")
        if not uid or not m.get("creationTimestamp"):
            continue
        rec = pods.setdefault(uid, {"created": ts(m["creationTimestamp"]), "ready": None})
        for c in (o.get("status", {}) or {}).get("conditions", []) or []:
            if c.get("type") == "Ready" and c.get("status") == "True" and c.get("lastTransitionTime") and rec["ready"] is None:
                rec["ready"] = ts(c["lastTransitionTime"])
    waits = [((r["ready"] if r["ready"] is not None else t1) - r["created"]) for r in pods.values() if t0 <= r["created"] <= t1]
    waits = [max(0.0, w) for w in waits]
    return {"pods started": float(len(waits)), "pod start wait, total (s)": float(sum(waits)),
            "pod start wait, mean (s)": float(sum(waits) / len(waits)) if waits else 0.0}


LOWER_BETTER = {"worker nodes in service, mean", "node-hours", "power (W), mean", "power (W), peak", "energy (Wh)",
                "energy, parked workers still on at idle power (Wh)",
                "energy per core-hour (Wh)", "node-hours per core-hour", "pending pods, pod-minutes", "pending pods, peak",
                "HPA shortfall (desired > current), minutes", "HPA replicas, mean", "pods started", "pod start wait, total (s)",
                "pod start wait, mean (s)", "response time (ms), mean", "response time (ms), median",
                "response time (ms), 95th percentile", "response time (ms), 99th percentile", "failed requests (%)"}
HIGHER_BETTER = {"utilisation (used / allocatable)", "CPU used (cores), mean"}


def latency(path):
    import csv
    if not path or not Path(path).exists():
        return {}
    r = list(csv.DictReader(open(path)))
    ok = np.array([float(x["latency_ms"]) for x in r if x["ok"] == "1"]); n = len(r)
    if not len(ok):
        return {"requests timed": float(n), "failed requests (%)": 100.0}
    return {"requests timed": float(n), "response time (ms), mean": float(ok.mean()),
            "response time (ms), median": float(np.percentile(ok, 50)), "response time (ms), 95th percentile": float(np.percentile(ok, 95)),
            "response time (ms), 99th percentile": float(np.percentile(ok, 99)),
            "failed requests (%)": 100.0 * (n - len(ok)) / max(n, 1)}


def timeline(rows, minute):
    out = {}
    for r in rows:
        m = int(F(r, "elapsed_seconds") // 60)
        out.setdefault(m, []).append(r)
    return {m: {"nodes": np.mean([F(r, "nodes_ready") for r in v]), "power": np.nanmean([F(r, "power_w") for r in v]),
                "replicas": np.mean([F(r, "hpa_current_replicas") for r in v]), "pending": np.mean([F(r, "pods_pending") for r in v]),
                "cpu": np.mean([F(r, "used_cpu_m") for r in v]) / 1000} for m, v in sorted(out.items())}


def fmt(v):
    return "n/a" if v != v else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}" if abs(v) >= 1 else f"{v:.3f}")


def report(native_csv, omni_csv, audit=None, kill=None, block_minutes=2.0, idle_w=100.0, dyn_w=150.0):
    N, O = load(native_csv), load(omni_csv)
    gn, go = gauges(N), gauges(O)
    ln, lo_ = latency(str(Path(native_csv).with_name("latency.csv"))), latency(str(Path(omni_csv).with_name("latency.csv")))
    for k in ln:
        gn[k], go[k] = ln[k], lo_.get(k, float("nan"))
    L = ["# Omni-Compass benchmark: Kubernetes native vs Kubernetes + Omni-Compass", "",
         "Two identical kind clusters (1 control plane + 6 workers), same add-ons, workload (php-apache + HPA, target 50),",
         "load schedule and capture. **Native**: Omni-Compass not running. **Omni**: Omni-Compass drives the HPA target, the",
         "node pool (cordon/drain/uncordon), the power cap (in-place CPU limits on the app pods, enforced by the kernel), heat",
         "(harness law on live power), security (hold signal) and the rollout guard. Response times are real HTTP requests timed",
         "every 5 s. Power is a declared model (idle 100 W + 150 W x utilisation per worker in service; parked workers on",
         "standby at idle power), not a meter.", "",
         "## Gauges", "", "| Gauge | Native | Omni-Compass | Change |", "|---|---:|---:|---:|"]
    for k in gn:
        a, b = gn[k], go[k]
        ch = "" if k == "duration (min)" or a != a or b != b else (f"{100 * (b - a) / a:+.1f}%" if a else ("0" if b == 0 else "new"))
        tag = ""
        if ch and k in LOWER_BETTER and b != a:
            tag = " better" if b < a else " worse"
        elif ch and k in HIGHER_BETTER and b != a:
            tag = " better" if b > a else " worse"
        L.append(f"| {k} | {fmt(a)} | {fmt(b)} | {ch}{tag} |")
    B = blocks(N, block_minutes * 60, idle_w, dyn_w); Ob = blocks(O, block_minutes * 60, idle_w, dyn_w)
    L += ["", f"## Significance ({block_minutes:g}-minute blocks: native {len(B)}, omni {len(Ob)}; bootstrap 95% interval)", "",
          "| Metric | Native | Omni-Compass | Change | 95% CI of difference | Verdict |", "|---|---:|---:|---:|---|---|"]
    for m, r in compare(B, Ob).items():
        rel = f"{100 * r['relative']:+.1f}%" if r["relative"] == r["relative"] else "n/a"
        L.append(f"| {m} | {r['baseline']:.4f} | {r['omni']:.4f} | {rel} | [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}] | {r['verdict']} |")
    if audit and Path(audit).exists():
        recs = [json.loads(l) for l in Path(audit).read_text().splitlines() if l.strip()]
        dec = [r["decision"] for r in recs if isinstance(r.get("decision"), dict)]
        L += ["", "## What Omni-Compass did", "",
              f"- decisions: {len(dec)} (one per minute)",
              f"- HPA target writes: {sum(1 for r in recs if 'HPA target to rho' in str(r.get('why', '')))}",
              f"- node-pool resizes: {sum(1 for r in recs if r.get('why') == 'node pool size')}",
              f"- scheduling-floor adds (pending pods): {sum(1 for r in recs if 'scheduling floor' in str(r.get('why', '')))}",
              f"- power-cap pod resizes (in place): {sum(1 for r in recs if str(r.get('why', '')).startswith('power_cap: pod'))}",
              f"- rollout actions: {sum(1 for r in recs if str(r.get('why', '')).startswith('rollout:'))}",
              f"- power cap decided per minute: {' '.join(str(d.get('power_cap', '')) for d in dec)}",
              f"- heat (thermal) per minute: {' '.join(str(d.get('thermal', '')) for d in dec)}",
              f"- nodes decided per minute: {' '.join(str(d['nodes_recommended']) for d in dec)}",
              f"- HPA target decided per minute (%): {' '.join(str(round(100 * d['hpa_target_recommended'])) for d in dec)}"]
    if kill and Path(kill).exists():
        L += ["", "## Kill switch", "", "```", Path(kill).read_text().strip(), "```"]
    tn, to = timeline(N, 60), timeline(O, 60)
    L += ["", "## Minute by minute", "",
          "| min | nodes native | nodes omni | power W native | power W omni | replicas native | replicas omni | pending native | pending omni | CPU native | CPU omni |",
          "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in sorted(set(tn) | set(to)):
        a, b = tn.get(m, {}), to.get(m, {})
        g = lambda d, k: fmt(d[k]) if k in d else ""
        L.append(f"| {m} | {g(a,'nodes')} | {g(b,'nodes')} | {g(a,'power')} | {g(b,'power')} | {g(a,'replicas')} | {g(b,'replicas')} | "
                 f"{g(a,'pending')} | {g(b,'pending')} | {g(a,'cpu')} | {g(b,'cpu')} |")
    L += ["", "## Limits", "",
          "- kind nodes are containers sharing one CI machine; timings and CPU are noisier than real servers.",
          "- The two arms ran on two different CI machines at the same time; machine-to-machine variation is part of the noise.",
          "- Energy is modelled from utilisation and nodes in service with the declared constants above.", ""]
    return "\n".join(L), gn, go


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--native", required=True); ap.add_argument("--omni", required=True)
    ap.add_argument("--audit"); ap.add_argument("--kill"); ap.add_argument("--out", default="BENCHMARK.md")
    ap.add_argument("--block-minutes", type=float, default=2.0)
    a = ap.parse_args(argv)
    md, gn, go = report(a.native, a.omni, a.audit, a.kill, a.block_minutes)
    Path(a.out).write_text(md)
    Path(a.out).with_suffix(".json").write_text(json.dumps({"native": gn, "omni": go}, indent=2))
    print(md)


if __name__ == "__main__":
    main()
