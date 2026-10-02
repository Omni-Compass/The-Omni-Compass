# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""CPU-frequency lever through the kernel's policy files (hardware/cpufreq.py, contract adopted from the ChatGPT
release, wired here under the nervous system). On a fake sysfs tree:
  C1 schedutil map: request = min(1, 1.25 u), tipping at u = 0.8
  C2 a ceiling never exceeds the operator's pre-Omni ceiling and never crosses scaling_min_freq
  C3 exact restore of every policy's pre-Omni ceiling (not the silicon maximum)
  C4 governor gate: refuses non-schedutil policies when required
  C5 the lever never sets a ceiling below the schedutil request at the current utilisation (no performance cut)
  C6 the lever stays inside the nervous-system envelope; the heat ceiling wins over the schedutil floor
  C7 kill switch restores the exact values, with an audit record"""
from pathlib import Path
from types import SimpleNamespace
import random, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hardware.cpufreq import CpuFreqPolicies, schedutil_frequency_invariant
from omni_controller.muscles import Muscles


def mkpolicy(root, name, cmin=800_000, cmax=3_200_000, smin=1_000_000, smax=2_800_000, driver="acpi-cpufreq",
             governor="schedutil", cpus="0 1"):
    p = root / name; p.mkdir(parents=True)
    for k, v in {"cpuinfo_min_freq": cmin, "cpuinfo_max_freq": cmax, "scaling_min_freq": smin, "scaling_max_freq": smax,
                 "scaling_driver": driver, "scaling_governor": governor, "affected_cpus": cpus}.items():
        (p / k).write_text(str(v))
    return p


def rd(p):
    return int((p / "scaling_max_freq").read_text())


def main():
    assert schedutil_frequency_invariant(0.0) == 0.0 and schedutil_frequency_invariant(0.4) == 0.5          # C1
    assert schedutil_frequency_invariant(0.8) == 1.0 and schedutil_frequency_invariant(0.95) == 1.0
    root = Path(tempfile.mkdtemp())
    p0 = mkpolicy(root, "policy0"); p2 = mkpolicy(root, "policy2", smin=900_000, smax=3_000_000, cpus="2 3")
    c = CpuFreqPolicies(root); c.capture_original(); c.assert_schedutil()
    c.apply_cap(0.75); assert rd(p0) == 2_100_000 and rd(p2) == 2_250_000                                   # C2
    c.apply_cap(0.10); assert rd(p0) == 1_000_000 and rd(p2) == 900_000
    c.restore(); assert rd(p0) == 2_800_000 and rd(p2) == 3_000_000                                          # C3
    other = Path(tempfile.mkdtemp()); mkpolicy(other, "policy0", driver="intel_pstate", governor="powersave")
    try:
        CpuFreqPolicies(other).assert_schedutil(); raise AssertionError("non-schedutil policy accepted")      # C4
    except RuntimeError as e:
        assert "schedutil required" in str(e)

    rng = random.Random(20260927); n = 0
    for _ in range(2000):                                                                                    # C5, C6
        live = Path(tempfile.mkdtemp()); smax = rng.choice([2_000_000, 2_600_000, 3_200_000])
        lp = mkpolicy(live, "policy0", smin=400_000, smax=smax, cmax=3_200_000)
        audit = []
        a = SimpleNamespace(cpufreq_policy_root=str(live), cpufreq_require_schedutil=True, cpufreq_cmd="", cpu_max_khz=0.0,
                            gpu_power_cmd="", gpu_max_w=0.0, cap_min=0.3, dry_run=False)
        m = Muscles(None, a, audit.append)
        lo = rng.uniform(0.6, 1.0); hi = rng.choice([1.0, rng.uniform(lo, 1.0)])
        m.auth = {"organs": {"cpufreq": {"envelope": [lo, hi]}}}
        u = rng.uniform(0.0, 1.0); cap = rng.uniform(0.3, 1.0)
        m._hardware(cap, {"slo_clean": True, "security_block": 0.0, "cpu_util": u})
        got = rd(lp) / smax
        want = min(max(max(a.cap_min, cap), lo, schedutil_frequency_invariant(u)), hi)
        if abs(max(a.cap_min, cap) - 1.0) < 0.02 and not audit:        # no change requested (cap at 1): nothing written
            assert rd(lp) == smax; continue
        assert abs(got - want) < 1e-5, (got, want, u, cap, lo, hi)
        assert got <= hi + 1e-6 and got >= min(lo, hi) - 1e-6                                                # C6
        assert got >= min(schedutil_frequency_invariant(u), hi) - 1e-6                                       # C5
        assert rd(lp) <= smax                                                                                 # C2
        m.restore(); assert rd(lp) == smax and any("cpu_pstate_restore" in r for r in audit)                  # C7
        n += 1
    print(f"cpufreq lever over {n:,} random (utilisation, cap, envelope) cases: schedutil floor, envelope, exact restore hold")
    print("PASS test_cpufreq_contract")


if __name__ == "__main__":
    main()
