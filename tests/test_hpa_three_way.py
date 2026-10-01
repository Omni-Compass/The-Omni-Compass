"""Three-way HPA agreement: fleet harness HPA, independent C++ HPA (test_cpp_hpa_parity), and an externally written
independent Python HPA (tests/third_party/hpa_independent.py).

The external implementation keeps recommendations with t >= cutoff (inclusive). Upstream Kubernetes keeps
recommendations whose timestamp is After(cutoff) (exclusive). At a fixed 15 s cadence the harness's 20-sample ring
is exactly the exclusive window (now - 300 s, now]. The test measures the inclusive disagreement and requires exact
agreement once the external window is made exclusive.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests" / "third_party"))
from hpa_independent import IndependentHPA
import fleet.sim as FS
from fleet.harness import make_scenario, hpa_step


class ExclusiveHPA(IndependentHPA):
    def windowed(self, now, rec, current):
        self.hist.append((now, rec)); cutoff = now - self.down_win
        self.hist = [(t, r) for t, r in self.hist if t > cutoff]
        return rec if rec >= current else max(r for _, r in self.hist)


def main(seeds=(901, 902)):
    streams, rid = {}, [None]

    def rec(w, target):
        st = streams.setdefault(f"{rid[0]}:{w.name}", {"lo": w.min_rep, "hi": w.max_rep, "r0": w.replicas, "steps": []})
        m, before = w.metric, w.replicas; hpa_step(w, target); st["steps"].append((m, before, w.replicas))
    FS.hpa_step = rec
    try:
        for v in ("web", "multi"):
            for s in seeds:
                rid[0] = f"{v}-{s}"; FS.run(make_scenario(v, s), "k8s_hpa70_ca")
    finally:
        FS.hpa_step = hpa_step
    res = {}
    for name, cls in (("inclusive", IndependentHPA), ("exclusive", ExclusiveHPA)):
        tot = bad = 0
        for st in streams.values():
            h = cls(target=0.70, lo=st["lo"], hi=st["hi"]); h.applied = st["r0"]
            for i, (m, before, after) in enumerate(st["steps"]):
                tot += 1; bad += int(h.step(15 * i, before, m) != after)
        res[name] = (tot, bad)
    print(f"external HPA, inclusive window: {res['inclusive'][1]} / {res['inclusive'][0]} steps differ; "
          f"exclusive window (upstream): {res['exclusive'][1]} / {res['exclusive'][0]} differ")
    assert res["exclusive"][1] == 0
    print("PASS test_hpa_three_way")
    return res


if __name__ == "__main__":
    main()
