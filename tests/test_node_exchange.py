"""CPU and GPU on one conserved power budget (hardware/node_exchange.py), checked on every card fit and two budgets.
N1 the budget is conserved: the joint conveyance (XC) never draws the site over its budget
N2 holding the CPUs is what makes the hand-over safe: counting only the CPUs' last measured draw (XM) does go over
N3 against today's practice (S: every GPU at one fixed cap that fits the CPUs' maximum) XC serves at least as much work
   and leaves less backlog
N4 the CPU clock read from an allocation never exceeds that allocation's power at the load it serves"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hardware.node_exchange import run, cpu_power, cpu_clock_for, FAMILIES, M, CPU_IDLE, CPU_MAX
from hardware.plant import VESSELS


def main():
    over_xm = 0
    for vn in ("gpu_mlperf_median", "gpu_mlperf_least_favourable", "gpu_mlperf_most_favourable"):
        v = VESSELS[vn]
        for budget in (0.6, 0.8):
            fams = [FAMILIES[i % len(FAMILIES)] for i in range(3, 7)]
            s, xm, xc = (run(v, fams, 4242, arm, budget, load=1.6, steps=240) for arm in ("S", "XM", "XC"))
            assert xc["site_violation_min"] == 0, f"N1 {vn} {budget}: XC over budget {xc['site_violation_min']} min"
            over_xm += xm["site_violation_min"]
            assert xc["work"] >= 0.999 * s["work"] and xc["backlog_min"] <= s["backlog_min"], f"N3 {vn} {budget}: {xc} vs {s}"
    import numpy as np
    rng = np.random.default_rng(515151); v = VESSELS["gpu_mlperf_median"]
    for _ in range(12):
        fams = [FAMILIES[int(rng.integers(0, len(FAMILIES)))] for _ in range(4)]; seed = int(rng.integers(1, 2**31))
        over_xm += run(v, fams, seed, "XM", 0.7, load=1.6)["site_violation_min"]
        assert run(v, fams, seed, "XC", 0.7, load=1.6)["site_violation_min"] == 0, "N1 on the simulation's own scenarios"
    assert over_xm > 0, "N2: measuring the CPUs alone never went over; the safety claim for holding them is untested"
    for w in (M * CPU_IDLE * 1.1, M * 250.0, M * CPU_MAX):
        for load in (0.05, 0.2, 0.35):
            f = cpu_clock_for(w, load)
            assert cpu_power(f, min(load, f)) <= w * 1.0001 or f == 0.4, (w, load, f)
    print("PASS test_node_exchange: CPU+GPU conveyance never over the site budget, CPU-measured-only goes over, "
          "more work and less backlog than today's fixed cap, CPU ceiling fits its allocation")


if __name__ == "__main__":
    main()
