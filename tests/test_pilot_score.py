"""pilot/score.py on generated captures: a real efficiency gain is detected, identical clusters show no significant
difference, a service regression is detected, measured power is used when present."""
import csv, sys, tempfile
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from pilot.score import main as score
F = ["timestamp", "elapsed_seconds", "nodes_ready", "nodes_total", "alloc_cpu_m", "req_cpu_m", "used_cpu_m", "pods_pending",
     "hpa_count", "hpa_current_replicas", "hpa_desired_replicas", "power_w"]


def capture(path, nodes, seed, pending_rate=0.0, power=False):
    rng = np.random.default_rng(seed)
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(F)
        for i in range(24 * 240):
            t = 15 * i; used = 40000 * (1 + 0.4 * np.sin(2 * np.pi * t / 86400)) * (1 + 0.05 * rng.standard_normal())
            pend = int(rng.random() < pending_rate) * 3
            pw = nodes * (200 + 350 * min(1.0, used / (nodes * 32000))) if power else ""
            w.writerow(["", t, nodes, nodes, nodes * 32000, 60000, int(used), pend, 5, 20, 20 + pend, pw])


def main():
    t = Path(tempfile.mkdtemp())
    capture(t / "base.csv", 20, 1); capture(t / "omni.csv", 12, 2); capture(t / "same.csv", 20, 3)
    capture(t / "bad.csv", 12, 4, pending_rate=0.3)
    capture(t / "base_p.csv", 20, 5, power=True); capture(t / "omni_p.csv", 12, 6, power=True)
    r = score(["--baseline", str(t / "base.csv"), "--omni", str(t / "omni.csv"), "--idle-w", "200", "--dyn-w", "350"])["metrics"]
    assert r["node_hours_per_core_hour"]["verdict"] == "better" and r["kwh_per_core_hour"]["verdict"] == "better"
    assert r["utilisation"]["verdict"] == "better" and r["pending_pod_minutes_per_hour"]["verdict"] == "no significant difference"
    s = score(["--baseline", str(t / "base.csv"), "--omni", str(t / "same.csv"), "--idle-w", "200", "--dyn-w", "350"])["metrics"]
    assert all(v["verdict"] == "no significant difference" for k, v in s.items() if k != "pending_pod_minutes_per_hour"), s
    b = score(["--baseline", str(t / "base.csv"), "--omni", str(t / "bad.csv")])["metrics"]
    assert b["pending_pod_minutes_per_hour"]["verdict"] == "worse" and b["hpa_shortfall_minutes_per_hour"]["verdict"] == "worse"
    p = score(["--baseline", str(t / "base_p.csv"), "--omni", str(t / "omni_p.csv")])["metrics"]
    assert p["kwh_per_core_hour"]["verdict"] == "better"
    print("pilot score: gain detected; identical clusters show no significant difference; service regression detected; measured power used")
    print("PASS test_pilot_score")


if __name__ == "__main__":
    main()
