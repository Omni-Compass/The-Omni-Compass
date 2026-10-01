"""schedutil model: the 1.25 map tips at 80% utilisation, OPP snap, uclamp, RT to policy max, rate limit, iowait boost,
and the Omni-Compass ceiling (scaling_max_freq) with the kill switch restoring cpuinfo_max_freq."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hardware.schedutil import Policy, next_freq, resolve, update, set_ceiling, SCALE

OPPS = [800_000, 1_200_000, 1_600_000, 2_000_000, 2_400_000, 2_800_000, 3_200_000]


def main():
    p = Policy(OPPS, rate_limit_us=0)
    fmax = p.cpuinfo_max
    # the >> 2 is the 1.25: at util = 0.8 x max the request reaches f_max
    assert next_freq(p, int(0.8 * SCALE)) >= fmax - 5_000, next_freq(p, int(0.8 * SCALE))
    assert next_freq(p, SCALE // 2) == (fmax + (fmax >> 2)) * (SCALE // 2) // SCALE
    # resolve: lowest OPP >= request
    assert resolve(p, 1_300_000) == 1_600_000 and resolve(p, 1_600_000) == 1_600_000 and resolve(p, 10) == 800_000
    assert update(p, 0, SCALE // 2) == 2_000_000          # 0.5 x 1.25 x 3.2 GHz = 2.0 GHz
    # uclamp caps what schedutil sees
    q = Policy(OPPS, rate_limit_us=0, uclamp_max=SCALE // 2)
    assert update(q, 0, SCALE) == 2_000_000
    # RT / deadline go to policy max, ignoring the map
    assert update(Policy(OPPS, rate_limit_us=0), 0, 10, rt=True) == fmax
    # Omni-Compass ceiling: schedutil still chooses, but never above scaling_max_freq
    set_ceiling(p, 2_200_000)
    assert update(p, 1, SCALE) == 2_000_000               # highest OPP <= the ceiling
    assert update(p, 2, 10, rt=True) == 2_000_000          # even RT stays under the policy ceiling
    assert update(p, 3, SCALE // 4) == 1_200_000           # below the ceiling schedutil is unchanged
    set_ceiling(p, None)                                   # kill switch
    assert p.scaling_max == fmax and update(p, 4, SCALE) == fmax
    # rate limit: requests inside the window are dropped, a lowered ceiling applies at once
    r = Policy(OPPS, rate_limit_us=1000)
    assert update(r, 0, SCALE) == fmax
    assert update(r, 500, 10) == fmax                      # dropped
    set_ceiling(r, 1_600_000)
    assert update(r, 600, SCALE) == 1_600_000              # ceiling enforced inside the window
    assert update(r, 5000, 10) == 800_000                  # outside the window the request goes through
    # iowait boost lifts a low util after IO wakeups and decays
    b = Policy(OPPS, rate_limit_us=0)
    f1 = update(b, 0, 10, iowait_wakeup=True); f2 = update(b, 1, 10, iowait_wakeup=True); f3 = update(b, 2, 10)
    assert f1 <= f2 and f3 <= f2
    print("PASS test_schedutil")


if __name__ == "__main__":
    main()
