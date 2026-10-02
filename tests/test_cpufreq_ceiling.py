# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""scripts/cpufreq_ceiling.sh against a fake sysfs: sets scaling_max_freq on every policy, clamps to cpuinfo limits,
restore puts cpuinfo_max_freq back, and fails loudly when there is no cpufreq."""
import os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def run(sysfs, arg):
    return subprocess.run(["bash", str(ROOT / "scripts/cpufreq_ceiling.sh"), arg], env=dict(os.environ, SYSFS=sysfs),
                          capture_output=True, text=True)


def main():
    t = tempfile.mkdtemp()
    for i, (lo, hi) in enumerate([(800000, 3200000), (1000000, 2400000)]):
        d = Path(t) / f"policy{i}"; d.mkdir()
        (d / "cpuinfo_min_freq").write_text(f"{lo}\n"); (d / "cpuinfo_max_freq").write_text(f"{hi}\n")
        (d / "scaling_max_freq").write_text(f"{hi}\n"); (d / "scaling_governor").write_text("schedutil\n")
    read = lambda i: int((Path(t) / f"policy{i}" / "scaling_max_freq").read_text())
    assert run(t, "2600000.4").returncode == 0 and read(0) == 2600000 and read(1) == 2400000
    assert run(t, "100").returncode == 0 and read(0) == 800000 and read(1) == 1000000
    assert run(t, "restore").returncode == 0 and read(0) == 3200000 and read(1) == 2400000
    assert run(tempfile.mkdtemp(), "restore").returncode != 0
    print("PASS test_cpufreq_ceiling")


if __name__ == "__main__":
    main()
