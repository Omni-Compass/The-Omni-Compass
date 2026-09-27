"""End-to-end self-pilot: the shipped controller in nodepool mode (default headroom) against the simulated cluster for one
day, captured and scored with pilot/score.py against HPA + Cluster Autoscaler on identical traffic. I never loosen the
operator's own HPA target (fewer, fuller pods always lengthen the wait), so on this plant my machines match the
autoscaler's: energy and node-hours per core-hour no worse, and no significant increase in pending-pod time."""
import sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from pilot.selfpilot import main as selfpilot


def main(seed=424242):
    res, out = selfpilot(["--seed", str(seed), "--days", "1", "--out", tempfile.mkdtemp()])
    m = res["metrics"]
    assert m["kwh_per_core_hour"]["verdict"] != "worse" and m["node_hours_per_core_hour"]["verdict"] != "worse", m
    assert m["pending_pod_minutes_per_hour"]["verdict"] != "worse", m["pending_pod_minutes_per_hour"]
    print(f"self-pilot: energy per core-hour {100 * m['kwh_per_core_hour']['relative']:+.1f}%, node-hours per core-hour "
          f"{100 * m['node_hours_per_core_hour']['relative']:+.1f}%, pending-pod time {m['pending_pod_minutes_per_hour']['verdict']}, "
          f"HPA shortfall {m['hpa_shortfall_minutes_per_hour']['verdict']}")
    print("PASS test_selfpilot")
    return res


if __name__ == "__main__":
    main()
