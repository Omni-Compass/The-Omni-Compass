"""Machine-organ release gate (omnicompass/nervous_system.node_release_gate): attribution + coordination + headroom.
G1 granted only when every condition holds; G2 each condition alone blocks, with its reason; G3 the headroom proof is
the engine's own rho: util after release = used / ((n-1) per_node); G4 random: a grant never leaves the machines above rho
and never happens with pods waiting, pods scaling up, a live latency breach or no contraction authority."""
import random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omnicompass.nervous_system import node_release_gate

YES = {"organs": {"nodes": {"contract": True}}}; NO = {"organs": {"nodes": {"contract": False}}}


def main():
    ok = node_release_gate(6, 4000, 1700, 0, False, False, 0.8, YES)
    assert ok["ok"] and abs(ok["util_after"] - 1700 / 20000) < 1e-12                                     # G1, G3
    for args, why in [((1, 4000, 100, 0, False, False, 0.8, YES), "one machine left"),
                      ((6, 4000, 1700, 2, False, False, 0.8, YES), "pods waiting"),
                      ((6, 4000, 1700, 0, True, False, 0.8, YES), "pods scaling up"),
                      ((6, 4000, 1700, 0, False, True, 0.8, YES), "latency breached now"),
                      ((6, 4000, 17000, 0, False, False, 0.8, YES), "util after"),
                      ((6, 4000, 1700, 0, False, False, 0.8, NO), "no contraction authority")]:
        r = node_release_gate(*args); assert not r["ok"] and why in r["reason"], (why, r)                # G2
    rng = random.Random(7)
    for _ in range(200_000):                                                                              # G4
        n = rng.randint(1, 12); per = rng.choice([2000, 4000, 8000]); used = rng.uniform(0, n * per)
        pend = rng.choice([0, 0, 0, 1, 3]); up = rng.random() < 0.2; br = rng.random() < 0.2; rho = rng.uniform(0.5, 0.95)
        auth = YES if rng.random() < 0.7 else NO
        r = node_release_gate(n, per, used, pend, up, br, rho, auth)
        if r["ok"]:
            assert n > 1 and pend == 0 and not up and not br and auth is YES and used / ((n - 1) * per) <= rho + 1e-12
    print("PASS test_node_release_gate: attribution, coordination and headroom gate over 200,000 random states")


if __name__ == "__main__":
    main()
