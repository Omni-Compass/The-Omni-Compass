"""Replay a cluster capture (capture/kube_capture.sh schema) through the frozen fleet-mode governor in OBSERVE.

The recommended fleet is carried forward as the governor's own counterfactual state (the node count it would have
reached), with load re-expressed against that fleet; the plant's response to the recommendation is not modelled.
Outputs, per decision (every FLEET_DECISION_SECONDS): the observed node count and Omni-Compass's recommended node count,
power cap and HPA target, with the scheduling floor (never fewer nodes than running pod requests need). The summary
compares observed node-hours with recommended node-hours and, if a node power model is supplied or power was captured,
an estimated energy difference. All outputs are counterfactual recommendations; nothing is applied to the cluster.
"""
import argparse, csv, json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.adapter import Governor, mode_law, FLEET_DECISION_SECONDS, OBSERVE

FIELDS = ["timestamp", "elapsed_seconds", "nodes_ready", "nodes_total", "alloc_cpu_m", "req_cpu_m", "used_cpu_m",
          "pods_pending", "hpa_count", "hpa_current_replicas", "hpa_desired_replicas", "power_w"]


def load(path):
    rows = list(csv.DictReader(open(path)))
    missing = [f for f in FIELDS if f not in rows[0]]
    if missing:
        raise ValueError(f"capture missing fields: {missing}")
    return rows


def replay(rows, idle_w=None, dyn_w=None, site_limit_w=None, min_nodes=1, max_nodes=10000):
    g = Governor(law=mode_law("fleet")); g.set_mode(OBSERVE)
    out, last_t, rec_n = [], None, None
    for r in rows:
        t = float(r["elapsed_seconds"])
        if last_t is not None and t - last_t < FLEET_DECISION_SECONDS:
            continue
        last_t = t
        n = max(1, int(float(r["nodes_ready"]))); alloc = max(1.0, float(r["alloc_cpu_m"]))
        per_node = alloc / n; req = float(r["req_cpu_m"]); used = float(r["used_cpu_m"])
        pend = int(float(r["pods_pending"]))
        pw = float(r["power_w"]) if r.get("power_w") not in (None, "") else None
        if rec_n is None:
            rec_n = n
        q = min(2.0, pend / max(1.0, float(r["hpa_current_replicas"]) or n))
        obs = {"queue_ratio": q, "load_ratio": min(2.0, used / max(1.0, rec_n * per_node)), "power_stress": (pw / site_limit_w) if (pw and site_limit_w) else 0.0,
               "thermal": 0.0, "network_stress": 0.0, "drift_ratio": 0.0, "stale": 0.0, "security_block": 0.0}
        g.nodes = rec_n; g.current_cap = 1.0
        d = g.step(obs, 0)
        floor = int(math.ceil(req / per_node)) if req > 0 else min_nodes
        rec = max(min_nodes, min(max_nodes, max(rec_n + int(d["node_delta"]), floor, int(math.ceil(used / per_node)))))
        rec_n = rec
        out.append({"elapsed_seconds": t, "nodes_observed": n, "nodes_recommended": rec, "power_cap_recommended": d["power_cap"],
                    "hpa_target_recommended": max(0.5, min(0.95, d["demand"])), "E": d["state"]["E"], "U": d["state"]["U"],
                    "used_cpu_m": used, "alloc_cpu_m": alloc, "power_w": pw})
    hrs = FLEET_DECISION_SECONDS / 3600.0
    obs_nh = sum(o["nodes_observed"] for o in out) * hrs; rec_nh = sum(o["nodes_recommended"] for o in out) * hrs
    summ = {"decisions": len(out), "observed_node_hours": obs_nh, "recommended_node_hours": rec_nh,
            "node_hours_change": rec_nh - obs_nh, "label": "counterfactual recommendation; not applied, not measured"}
    if idle_w is not None and dyn_w is not None:
        e = lambda nodes, used, per: nodes * (idle_w + dyn_w * min(1.0, used / max(1.0, nodes * per)))
        eo = sum(e(o["nodes_observed"], o["used_cpu_m"], o["alloc_cpu_m"] / o["nodes_observed"]) for o in out) * hrs / 1000
        er = sum(e(o["nodes_recommended"], o["used_cpu_m"], o["alloc_cpu_m"] / o["nodes_observed"]) for o in out) * hrs / 1000
        summ.update({"estimated_energy_observed_kwh": eo, "estimated_energy_recommended_kwh": er, "power_model_w": [idle_w, dyn_w]})
    return out, summ


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("capture"); ap.add_argument("--out", default="replay")
    ap.add_argument("--idle-w", type=float); ap.add_argument("--dyn-w", type=float); ap.add_argument("--site-limit-w", type=float)
    a = ap.parse_args()
    out, summ = replay(load(a.capture), a.idle_w, a.dyn_w, a.site_limit_w)
    o = Path(a.out); o.mkdir(parents=True, exist_ok=True)
    with open(o / "DECISIONS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    (o / "SUMMARY.json").write_text(json.dumps(summ, indent=2)); print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
