"""C++ shield (cpp/src/shield.cpp) vs Python shield (omnicompass/shield.py) on action sets recorded from the benchmark."""
import csv, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import benchmarks.stack_benchmark as B
from omnicompass import stack_sim as S
from omnicompass import shield as SH
from omnicompass.adapter import AllocationLaw


def main(exe, n=20):
    cases = []
    orig_enforce, orig_viol = B.enforce, B.violations

    def rec(acts, st, obs, cfg, lim=SH.ShieldLimits()):
        cases.append((acts, st, obs, cfg, lim)); return orig_enforce(acts, st, obs, cfg, lim)

    def rec_v(acts, st, obs, cfg, lim=SH.ShieldLimits()):
        cases.append((acts, st, obs, cfg, lim)); return orig_viol(acts, st, obs, cfg, lim)
    B.enforce, B.violations = rec, rec_v
    cfg = S.ManagerBenchmarkConfig(profile="full", scenarios=n, steps=72)
    for s in S._mom_generate_scenarios(cfg, 515151)[:n]:
        for arm in ("omni_direct", "omni_direct_no_shield", "omni_k8s_protect", "omni_k8s_throughput", "k8s_ref_70"):
            B.simulate(s, arm, cfg, AllocationLaw())
    B.enforce, B.violations = orig_enforce, orig_viol
    tmp = Path(tempfile.mkdtemp())
    with open(tmp / "cases.csv", "w", newline="") as f:
        f.write("case,nodes,cap,power_stress,security,min_nodes,max_nodes,power_limit,actions\n")
        for i, (acts, st, obs, c, lim) in enumerate(cases):
            a = ";".join(f"{x['action']}:{float(x['target'])!r}:{int(x['direction'])}" for x in acts)
            f.write(f"{i},{int(st['actual_nodes'])},{float(st['power_cap'])!r},{float(obs.get('power_stress', 0.0))!r},"
                    f"{float(obs.get('security_block', 0.0))!r},{c.minimum_nodes},{c.maximum_nodes},{lim.power_limit!r},{a}\n")
    subprocess.run([exe, str(tmp / "cases.csv"), str(tmp / "out.csv")], check=True, capture_output=True)
    got = list(csv.DictReader(open(tmp / "out.csv")))
    bad = 0
    for (acts, st, obs, c, lim), g in zip(cases, got):
        ea, eh = orig_enforce([dict(x) for x in acts], st, obs, c, lim)
        ev = orig_viol(acts, st, obs, c, lim)
        py_e = ";".join(f"{x['action']}:{float(x['target'])!r}:{int(x['direction'])}" for x in ea)
        cp_e = ";".join(f"{p.split(':')[0]}:{float(p.split(':')[1])!r}:{p.split(':')[2]}" for p in g["enforced"].split(";") if p)
        bad += int(int(g["interventions"]) != eh or py_e != cp_e or ";".join(ev) != g["violations"])
    print(f"C++ vs Python shield: {len(cases)} action sets, mismatches = {bad}")
    assert len(got) == len(cases) and bad == 0
    print("PASS test_cpp_shield_parity")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "cpp" / "build" / "oc_shield"))
