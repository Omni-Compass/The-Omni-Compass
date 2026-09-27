"""Invariants of the supervisory nervous system (omnicompass/nervous_system.py) over random and adversarial states.
N1 observe executes nothing; N2 kill leaves no authority; N3 a security hold lets no capacity organ expand (cooling is protective: more cooling adds no capacity); N4 more stress (S),
more push, more unmet need (I_U) or a lower U never grants more contraction authority to any organ; N5 every envelope
lies inside its hardware range (cpufreq and GPU ceilings in [0.65, 1], power cap [0.65, 1], shift [0, 0.5], cooling
[18, 27]); N6 deterministic. Usage: python tests/test_nervous_system.py [cases]"""
import random, sys
from dataclasses import replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.nervous_system import authority, NervousInputs

RANGES = {"cpufreq": (0.65, 1.0), "gpu": (0.65, 1.0), "power": (0.65, 1.0), "routing": (0.0, 0.5), "cooling": (18.0, 27.0)}


def rnd(r):
    return NervousInputs(E=r.uniform(-2, 3), U=r.choice([r.uniform(-1.5, 1.5), 1.0, 0.5, -1.0]), I_U=r.uniform(-1, 3),
                         S=r.choice([r.uniform(0, 6), 0.0, 2.37]), push=r.choice([0.0, 0.2, r.uniform(0, 3)]), s_eq=r.choice([2.37, 1.0, 0.5]),
                         security_block=r.choice([0.0, 0.0, 1.0, r.random()]), slo_clean=r.random() < 0.8,
                         power_stress=r.uniform(0, 1.5), thermal=r.uniform(0, 1.3), rollback=r.random() < 0.2,
                         mode=r.choice(["autopilot", "observe"]), killed=r.random() < 0.05)


def contract_vec(a):
    return {o: (v.get("contract", False), v.get("step", 0.0)) for o, v in a["organs"].items()}


def main(n=300_000):
    r = random.Random(7); bad = {k: 0 for k in ("N1", "N2", "N3", "N4", "N5", "N6")}
    for _ in range(n):
        i = rnd(r); a = authority(i)
        if i.mode == "observe" and a["execute"]: bad["N1"] += 1
        if i.killed and (a["execute"] or a["organs"]): bad["N2"] += 1
        if i.killed:
            continue
        if i.security_block > 0.5 and any((v.get("expand") or v.get("admit")) and not v.get("protective") for o, v in a["organs"].items()): bad["N3"] += 1
        worse = [replace(i, S=i.S + r.uniform(0, 2)), replace(i, push=i.push + r.uniform(0, 2)),
                 replace(i, I_U=i.I_U + r.uniform(0, 2)), replace(i, U=i.U - r.uniform(0, 1))]
        base = contract_vec(a)
        for j in worse:
            b = contract_vec(authority(j))
            if any((b[o][0] and not base[o][0]) or b[o][1] > base[o][1] + 1e-12 for o in base):
                bad["N4"] += 1; break
        for o, (lo, hi) in RANGES.items():
            e = a["organs"][o]["envelope"]
            if not (lo - 1e-9 <= e[0] <= e[1] <= hi + 1e-9): bad["N5"] += 1
        if authority(i) != a: bad["N6"] += 1
    print(f"nervous-system invariants over {n:,} states:", bad)
    assert not any(bad.values()), bad
    print("PASS test_nervous_system")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300_000)
