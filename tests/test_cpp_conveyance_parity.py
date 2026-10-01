"""C++ conveyance law (cpp/src/conveyance.cpp) vs Python conveyance law (omnicompass/conveyance.py Conveyance) on random
systems (2 to 12 organs, random budgets, needs, floors and ceilings, needs that rise and fall over 40 steps) and on the
CPU+GPU organ layout of hardware/node_exchange.py: the same allocations at every step, to 1e-9 of the budget.
Usage: python tests/test_cpp_conveyance_parity.py OC_CONVEYANCE [systems]"""
import random, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.conveyance import Conveyance


def case(rng):
    n = rng.randint(2, 12); budget = rng.uniform(50, 5000); rho = rng.uniform(0.5, 0.95); kappa = rng.uniform(0.2, 3.0)
    hi = [rng.uniform(0.2, 1.0) * budget for _ in range(n)]
    lo = [rng.uniform(0.0, 0.4) * h for h in hi]
    base = [rng.uniform(0.0, 1.2) * h for h in hi]
    steps = [[max(0.0, b * (1 + 0.5 * rng.uniform(-1, 1))) for b in base] for _ in range(40)]
    return n, budget, rho, kappa, lo, hi, steps


def node_layout():
    g_hi, c_hi = 16 * 700.0, 4 * 400.0
    lo = [16 * 700.0 * 300 / 700] * 4 + [4 * 120.0 * 1.05] * 4
    hi = [g_hi] * 4 + [c_hi] * 4
    rng = random.Random(515151)
    steps = [[rng.uniform(0.3, 1.0) * h for h in hi] for _ in range(60)]
    return 8, 0.7 * (4 * g_hi + 4 * c_hi), 0.8, 1.0, lo, hi, steps


def compare(exe, n, budget, rho, kappa, lo, hi, steps, d):
    fin = d / "in.csv"; fout = d / "out.csv"
    fin.write_text(f"{n},{budget!r},{rho!r},{kappa!r}\n" + "".join(",".join(repr(x) for x in s + lo + hi) + "\n" for s in steps))
    subprocess.run([exe, str(fin), str(fout)], check=True)
    cpp = [[float(x) for x in l.split(",")] for l in fout.read_text().splitlines() if l]
    cv = Conveyance(n, budget, rho=rho, kappa=kappa)
    worst = 0.0
    for t, s in enumerate(steps):
        py = cv.step(s, lo, hi)
        worst = max(worst, max(abs(p - c) for p, c in zip(py, cpp[t])) / budget)
    return worst


def main(exe, systems=200):
    rng = random.Random(20260928); d = Path(tempfile.mkdtemp())
    worst = max(compare(exe, *case(rng), d) for _ in range(systems))
    worst = max(worst, compare(exe, *node_layout(), d))
    assert worst < 1e-9, f"C++ and Python conveyance differ by {worst:.3e} of the budget"
    print(f"PASS test_cpp_conveyance_parity: {systems} random systems x 40 steps and the CPU+GPU layout, "
          f"worst difference {worst:.1e} of the budget")
    return worst


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 200)
