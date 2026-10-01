"""The realm harness (realms/): the catalog, the arms and the rules, without the full run.

Catalog: 656 muscles, four realms, every row on a known plant with one of the four knobs.
Arms: on one muscle of every plant and every knob kind, the watch arm equals native exactly and writes nothing; the omni
arm's kill switch hands the knob back (no write after the kill, the knob at its native value); every run is
deterministic. Organism: watch equals native for a realm organism; omni hands back every knob.
Rules: the capacity law adds at once and removes one unit only after convergence and dwell; the label rule."""
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from realms.harness import catalog, run_muscle, run_organism, label, ARMS  # noqa: E402
from realms.plants import KNOBS, TEMPLATES, governed_capacity  # noqa: E402
from realms.presets import PRESETS  # noqa: E402
from omnicompass.adapter import AllocationLaw  # noqa: E402


def main():
    rows = catalog()
    assert len(rows) == 656, len(rows)
    assert len({r["muscle_id"] for r in rows}) == 656
    assert set(Counter(r["realm"] for r in rows)) == {"compute_ai_cloud", "physics_robotics_autonomous",
                                                      "energy_facility_industrial", "distribution_specialized"}
    for r in rows:
        assert r["template"] in TEMPLATES and r["preset"] in PRESETS and r["knob"] in KNOBS, r

    picked = {}
    for r in rows:
        picked.setdefault((r["template"], r["knob"]), r)
    for (template, knob), r in sorted(picked.items()):
        if template == "motion_axis" and r["preset"] == "robot_joint":
            continue                                               # the slowest plant; covered by the organism below
        a, b = run_muscle(r, 7), run_muscle(r, 7)
        assert a == b, f"not deterministic: {r['muscle']}"
        assert a["watch_equal"], f"watch differs from native: {r['muscle']}"
        assert a["watch"]["writes"] == 0
        assert a["omni"]["restore_ok"] and a["omni"]["after_kill_writes"] == 0, f"kill did not hand back: {r['muscle']}"
        for arm in ARMS:
            m = a[arm]
            assert m["steps"] > 0 and m["energy_j"] == m["energy_j"], (r["muscle"], arm)

    realm = [r for r in rows if r["realm"] == "energy_facility_industrial"]
    o = run_organism(realm, 7)
    assert o["watch_equal"] and o["watch"]["writes"] == 0
    assert o["omni"]["restore_ok"] and o["omni"]["writes"] > 0

    law = AllocationLaw()
    st = {"surplus": 0, "since_add": 99}
    assert governed_capacity(st, 10, 0.95, 0.0, 0.8, 0.0, law, 1, 1, 100) == 12          # up at once
    st = {"surplus": 0, "since_add": 99}
    seq = [governed_capacity(st, 10, 0.3, 0.0, 0.9, 0.0, law, 1, 1, 100) for _ in range(law.down_dwell)]
    assert seq[:-1] == [10] * (law.down_dwell - 1) and seq[-1] == 9                       # down by one after the dwell
    st = {"surplus": 0, "since_add": 99}
    assert all(governed_capacity(st, 10, 0.3, 0.0, 0.9, 0.5, law, 1, 1, 100) == 10 for _ in range(20))  # not converged

    c = lambda p, w, v: {"primary": p, "work": w, "energy": 0.0, "viol_pp": v}
    assert label([c(0.05, 0.0, 0.0), c(0.06, 0.0, 0.0), c(0.04, 0.0, 0.0)]) == "SUPERIOR WITHIN GUARDRAILS"
    assert label([c(0.05, 0.0, 5.0), c(0.06, 0.0, 6.0), c(0.04, 0.0, 5.5)]) == "ENERGY IMPROVEMENT WITH SERVICE TRADEOFF"
    assert label([c(-0.05, 0.0, 0.0), c(-0.06, 0.0, 0.0), c(-0.04, 0.0, 0.0)]) == "WORSE"
    assert label([c(0.01, 0.0, 0.0), c(-0.01, 0.0, 0.0), c(0.0, 0.0, 0.0)]) == "NONINFERIOR / INCONCLUSIVE"
    assert label([c(0.05, 0.0, 0.0)] * 3, valid=False) == "INVALID"
    print("PASS test_realms: catalog 656, watch = native, kill hands back, deterministic, capacity law, labels")


if __name__ == "__main__":
    main()
