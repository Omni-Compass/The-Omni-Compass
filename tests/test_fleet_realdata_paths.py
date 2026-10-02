# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Capture replay and PlanetLab vessel on inputs in the exact real formats (generated here, not real data)."""
import csv, sys, tempfile
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet.capture_replay import replay, FIELDS
from fleet import planetlab as PL
from fleet.sim import run, arms_for


def cap(rows_spec):
    rows = []
    for i, (n, req, used, pend) in enumerate(rows_spec):
        rows.append(dict(zip(FIELDS, ["2026-01-01T00:00:00Z", str(15 * i), str(n), str(n), str(n * 32000), str(req), str(used),
                                       str(pend), "10", "40", "40", ""])))
    return rows


def main():
    over = cap([(20, 100000, 50000, 0)] * 480)
    out, s = replay(over, idle_w=200, dyn_w=350)
    assert all(o["nodes_recommended"] >= 4 for o in out)
    assert s["recommended_node_hours"] < s["observed_node_hours"]
    assert s["estimated_energy_recommended_kwh"] < s["estimated_energy_observed_kwh"]
    under = cap([(4, 120000, 118000, 30)] * 120)
    out2, _ = replay(under)
    assert all(o["nodes_recommended"] >= o["nodes_observed"] for o in out2)
    assert replay(over)[1] == replay(over)[1]
    print(f"capture replay: over-provisioned {s['observed_node_hours']:.1f} -> {s['recommended_node_hours']:.1f} node-hours "
          f"(never below the request floor); under-provisioned: never recommends fewer nodes; deterministic")
    d = Path(tempfile.mkdtemp()); rng = np.random.default_rng(3)
    for k in range(6):
        (d / f"vm_{k}").write_text("\n".join(str(int(x)) for x in np.clip(rng.normal(15, 10, 288), 0, 100)))
    tr = PL.load_dir(d); scn = PL.make_scenario(tr, 1)
    r = {a: run(scn, a) for a in arms_for("web")}
    assert r["omni_observe"]["trace_hash"] == r["k8s_hpa70_ca"]["trace_hash"]
    assert all(np.isfinite(x["energy_kwh"]) for x in r.values())
    print("PlanetLab vessel: format load, 12 workloads, all arms run, observe identical to HPA+CA")
    print("PASS test_fleet_realdata_paths")


if __name__ == "__main__":
    main()
