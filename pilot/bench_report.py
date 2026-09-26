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


LOWER_BETTER = {"worker nodes in service, mean", "node-hours", "power (W), mean", "power (W), peak", "energy (Wh)",
                "energy per core-hour (Wh)", "node-hours per core-hour", "pending pods, pod-minutes", "pending pods, peak",
                "HPA shortfall (desired > current), minutes", "response time (ms), mean", "response time (ms), median",
                "response time (ms), 95th percentile", "response time (ms), 99th percentile", "failed requests (%)"}
HIGHER_BETTER = {"utilisation (used / allocatable)"}


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
