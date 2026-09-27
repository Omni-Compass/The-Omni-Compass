"""C++ closure law (cpp/src/closure.cpp) vs Python closure law (omnicompass/closure.py ClosureNodes) on input sequences
recorded from the fleet plant (every workload type, the frozen settings of tuning/CLOSURE_FINAL_DEV.json, several
scenarios): identical machine targets and warm-reserve sizes at every tick.
Usage: python tests/test_cpp_closure_parity.py OC_CLOSURE [scenarios]"""
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario
from fleet.sim_slo import DirectLaw
from omnicompass.speed import SpeedLaw
from omnicompass import closure as C

FIELDS = ("rho_max", "delta", "H_add", "H_rel", "a", "b", "g", "push_release", "turn", "delta_rel", "z", "tone", "tone_H", "dwell")


def record(v, seed, f):
    rec = []
    orig = C.ClosureNodes.decide

    def dec(self, n, c, push, n_min, n_max):
        rec.append((self._last_r, n, c, push, n_min, n_max))
        return orig(self, n, c, push, n_min, n_max)
    oo = C.ClosureNodes.observe

    def obs(self, r, dt=1.0):
        self._last_r = r
        return oo(self, r, dt)
    C.ClosureNodes.decide, C.ClosureNodes.observe = dec, obs
    try:
        cl = {k: x for k, x in f["closure"].items() if k != "site"}
        sim_slo.run(make_scenario(v, seed), "omni_closure", speed_law=SpeedLaw(**f["speed"]), omni_every=1,
                    direct_law=DirectLaw(**f["direct"]), closure_law=C.ClosureLaw(**cl))
    finally:
        C.ClosureNodes.decide, C.ClosureNodes.observe = orig, oo
    return C.ClosureLaw(**cl), rec


def main(exe, n=3):
    F = {k: x for k, x in json.load(open(ROOT / "tuning/CLOSURE_FINAL_DEV.json")).items() if not k.startswith("_")}
    tmp = Path(tempfile.mkdtemp()); ticks = bad = 0
    for v in ("web", "batch", "gpu"):
        for seed in range(101, 101 + n):
            law, rec = record(v, seed, F[v])
            (tmp / "law.csv").write_text(",".join(FIELDS) + "\n" + ",".join(repr(float(getattr(law, k))) for k in FIELDS) + "\n")
            with open(tmp / "trace.csv", "w") as fh:
                fh.write("r,n,c,push,n_min,n_max\n")
                for r in rec:
                    fh.write(",".join(repr(float(x)) for x in r) + "\n")
            subprocess.run([exe, str(tmp / "law.csv"), str(tmp / "trace.csv"), str(tmp / "out.csv")], check=True)
            got = [tuple(map(int, line.split(","))) for line in (tmp / "out.csv").read_text().split()[1:]]
            py = C.ClosureNodes(law); want = []
            for r, nn, c, push, lo, hi in rec:
                py.observe(r); t = py.decide(int(nn), c, push, int(lo), int(hi)); want.append((t, py.reserve(c)))
            ticks += len(want); bad += sum(a != b for a, b in zip(got, want)) + abs(len(got) - len(want))
    print(f"C++ vs Python closure law: {ticks:,} decisions, mismatches = {bad}")
    assert bad == 0
    print("PASS test_cpp_closure_parity")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3)
