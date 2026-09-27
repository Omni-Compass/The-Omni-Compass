"""C++ shield vs Python shield on the adversarial generator of tests/test_shield_properties.py (rate limit 4, the value
the C++ fixture interface carries): enforced actions, intervention counts and violation lists must be identical, and the
C++ enforced sets must satisfy every invariant. Usage: python tests/test_cpp_shield_adversarial.py OC_SHIELD [cases]"""
import csv, random, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.shield import enforce, violations, ShieldLimits
from tests.test_shield_properties import case


def fmt(acts):
    return ";".join(f"{x['action']}:{float(x['target'])!r}:{int(x['direction'])}" for x in acts)


def main(exe, n=200_000):
    rng = random.Random(4242)
    cases = []
    for _ in range(n):
        acts, st, obs, cfg, lim = case(rng)
        lim = ShieldLimits(power_limit=lim.power_limit, max_node_step=4)
        acts = [dict(a, target=float(int(a["target"])) if a["action"] == "nodes" else float(a["target"])) for a in acts]
        cases.append((acts, st, obs, cfg, lim))
    tmp = Path(tempfile.mkdtemp())
    with open(tmp / "cases.csv", "w", newline="") as f:
        f.write("case,nodes,cap,power_stress,security,min_nodes,max_nodes,power_limit,actions\n")
        for i, (acts, st, obs, c, lim) in enumerate(cases):
            f.write(f"{i},{int(st['actual_nodes'])},{float(st['power_cap'])!r},{float(obs['power_stress'])!r},"
                    f"{float(obs['security_block'])!r},{c.minimum_nodes},{c.maximum_nodes},{lim.power_limit!r},{fmt(acts)}\n")
    subprocess.run([exe, str(tmp / "cases.csv"), str(tmp / "out.csv")], check=True, capture_output=True)
    got = list(csv.DictReader(open(tmp / "out.csv")))
    bad = 0
    for (acts, st, obs, c, lim), g in zip(cases, got):
        ea, eh = enforce([dict(x) for x in acts], st, obs, c, lim)
        ev = violations(acts, st, obs, c, lim)
        cp = ";".join(f"{p.split(':')[0]}:{float(p.split(':')[1])!r}:{p.split(':')[2]}" for p in g["enforced"].split(";") if p)
        bad += int(int(g["interventions"]) != eh or fmt(ea) != cp or ";".join(ev) != g["violations"])
    print(f"C++ vs Python shield, adversarial: {len(cases):,} cases, mismatches = {bad}")
    assert len(got) == len(cases) and bad == 0
    print("PASS test_cpp_shield_adversarial")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 200_000)
