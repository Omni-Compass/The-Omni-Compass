"""Score a pilot from your own cluster captures (fleet/capture/kube_capture.sh schema).

Compare a baseline capture (your normal autoscaling: a period before Omni-Compass, or a matched node pool) with an
Omni-Compass capture (a period or matched pool under the controller). Because traffic differs between periods and
pools, efficiency is normalised by the work actually done (CPU core-hours used):

  node-hours per used core-hour          lower is better
  energy per used core-hour (kWh)        lower is better; measured from power_w if captured, otherwise modelled
                                         from --idle-w / --dyn-w per node and utilisation
  mean CPU utilisation (used / allocatable)   higher is better
  pending-pod minutes per hour           service proxy, lower is better
  HPA shortfall minutes per hour         minutes with desired replicas above current replicas, lower is better

Each capture is cut into blocks (default 60 minutes). Differences between the Omni-Compass and baseline block means are
given with a bootstrap 95% interval over blocks; a verdict is stated only when the interval excludes zero.

python pilot/score.py --baseline baseline.csv --omni omni.csv [--idle-w 200 --dyn-w 350] [--block-minutes 60] [--out score.json]
"""
import argparse, csv, json, sys
from pathlib import Path
import numpy as np

LOWER = {"node_hours_per_core_hour": True, "kwh_per_core_hour": True, "utilisation": False,
         "pending_pod_minutes_per_hour": True, "hpa_shortfall_minutes_per_hour": True}


def load(path):
    rows = list(csv.DictReader(open(path)))
    need = ["elapsed_seconds", "nodes_ready", "alloc_cpu_m", "used_cpu_m", "pods_pending", "hpa_current_replicas", "hpa_desired_replicas"]
    miss = [f for f in need if f not in rows[0]]
    if miss:
        raise ValueError(f"{path}: missing fields {miss}")
    return rows


def blocks(rows, block_s, idle_w, dyn_w):
    out, cur, start = [], [], None
    for r in rows:
        t = float(r["elapsed_seconds"])
        start = t if start is None else start
        if t - start >= block_s and cur:
            out.append(cur); cur, start = [], t
        cur.append(r)
    if cur and (float(cur[-1]["elapsed_seconds"]) - float(cur[0]["elapsed_seconds"])) >= 0.5 * block_s:
        out.append(cur)
    res = []
    for b in out:
        ts = [float(r["elapsed_seconds"]) for r in b]
        dt = np.diff(ts + [ts[-1] + (ts[-1] - ts[-2] if len(ts) > 1 else 15.0)]) / 3600.0
        nodes = np.array([float(r["nodes_ready"]) for r in b]); alloc = np.array([float(r["alloc_cpu_m"]) for r in b]) / 1000.0
        used = np.array([float(r["used_cpu_m"]) for r in b]) / 1000.0; pend = np.array([float(r["pods_pending"]) for r in b])
        short = np.array([float(r["hpa_desired_replicas"]) > float(r["hpa_current_replicas"]) for r in b], float)
        core_h = float((used * dt).sum()); hours = float(dt.sum())
        pw = [r.get("power_w", "") for r in b]
        if all(p not in ("", None) for p in pw):
            kwh = float((np.array([float(p) for p in pw]) * dt).sum()) / 1000.0
        elif idle_w is not None and dyn_w is not None:
            util = np.clip(used / np.maximum(alloc, 1e-9), 0, 1)
            kwh = float((nodes * (idle_w + dyn_w * util) * dt).sum()) / 1000.0
        else:
            kwh = float("nan")
        res.append({"node_hours_per_core_hour": float((nodes * dt).sum()) / max(core_h, 1e-9),
                    "kwh_per_core_hour": kwh / max(core_h, 1e-9),
                    "utilisation": float((used * dt).sum() / max((alloc * dt).sum(), 1e-9)),
                    "pending_pod_minutes_per_hour": float((pend * dt).sum()) * 60.0 / max(hours, 1e-9),
                    "hpa_shortfall_minutes_per_hour": float((short * dt).sum()) * 60.0 / max(hours, 1e-9)})
    return res


def compare(base, omni, seed=12345, n=4000):
    rng = np.random.default_rng(seed); out = {}
    for m, lower in LOWER.items():
        a = np.array([b[m] for b in base]); c = np.array([b[m] for b in omni])
        if np.isnan(a).any() or np.isnan(c).any():
            continue
        diffs = c[rng.integers(0, len(c), (n, len(c)))].mean(1) - a[rng.integers(0, len(a), (n, len(a)))].mean(1)
        lo, hi = np.percentile(diffs, [2.5, 97.5]); d = float(c.mean() - a.mean())
        verdict = ("better" if (hi < 0) == lower else "worse") if (hi < 0 or lo > 0) else "no significant difference"
        out[m] = {"baseline": float(a.mean()), "omni": float(c.mean()), "difference": d,
                  "relative": d / a.mean() if a.mean() else float("nan"), "ci95": [float(lo), float(hi)], "verdict": verdict}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", required=True); ap.add_argument("--omni", required=True)
    ap.add_argument("--idle-w", type=float); ap.add_argument("--dyn-w", type=float)
    ap.add_argument("--block-minutes", type=float, default=60.0); ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    B = blocks(load(a.baseline), a.block_minutes * 60, a.idle_w, a.dyn_w)
    O = blocks(load(a.omni), a.block_minutes * 60, a.idle_w, a.dyn_w)
    if len(B) < 5 or len(O) < 5:
        print(f"warning: few blocks (baseline {len(B)}, omni {len(O)}); intervals will be wide", file=sys.stderr)
    res = {"blocks": {"baseline": len(B), "omni": len(O)}, "block_minutes": a.block_minutes, "metrics": compare(B, O)}
    for m, r in res["metrics"].items():
        rel = f"{100 * r['relative']:+6.1f}%" if r["relative"] == r["relative"] else "   n/a "
        print(f"{m:32s} baseline {r['baseline']:10.4f}  omni {r['omni']:10.4f}  change {rel}  "
              f"95% CI [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}]  {r['verdict']}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    main()
