"""Conveyance law (omnicompass/conveyance.py), the formal properties of docs/CONVEYANCE_LAW.md, checked numerically.
P1 conservation: the replicator step conserves the budget to 1e-9 relative
P2 Lyapunov: F(a) = sum (d_i/rho) ln a_i never decreases along the flow
P3 convergence: a -> A d / D exponentially at rate kappa D / (rho A) (checked against the closed form)
P4 projection: bounds hold, the budget is never exceeded, budget no organ can use is not spent
P5 the full law never allocates beyond the site budget, and every organ gets at least its floor"""
import math, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omnicompass.conveyance import replicator_step, project, Conveyance


def F(a, d, rho):
    return sum(di / rho * math.log(ai) for ai, di in zip(a, d))


def main():
    rng = random.Random(3)
    for _ in range(20_000):
        n = rng.randint(2, 8); A = rng.uniform(1, 100); rho = rng.uniform(0.5, 0.95); kappa = rng.uniform(0.1, 3)
        a = [rng.uniform(0.05, 1) for _ in range(n)]; a = [x * A / sum(a) for x in a]
        d = [rng.uniform(0.01, 2) * A / n for _ in range(n)]; D = sum(d)
        b = replicator_step(a, d, rho, kappa, dt=rng.uniform(0.01, 2))
        assert abs(sum(b) - A) <= 1e-9 * A                                                    # P1
        assert F(b, d, rho) >= F(a, d, rho) - 1e-9                                            # P2
        star = [A * di / D for di in d]
        dt = rng.uniform(0.1, 5); c = replicator_step(a, d, rho, kappa, dt)
        k = math.exp(-kappa * D * dt / (rho * A))
        assert all(abs((ci - si) - (ai - si) * k) < 1e-9 * A for ci, si, ai in zip(c, star, a))  # P3
        lo = [rng.uniform(0, 0.1) * A / n for _ in range(n)]; hi = [l + rng.uniform(0.05, 1) * A for l in lo]
        bud = rng.uniform(sum(lo), sum(hi))
        p = project([rng.uniform(0, A) for _ in range(n)], lo, hi, bud)
        assert all(l - 1e-9 <= x <= h + 1e-9 for x, l, h in zip(p, lo, hi)) and sum(p) <= bud + 1e-6    # P4
    for _ in range(2_000):                                                                   # P5
        n = rng.randint(2, 6); B = rng.uniform(50, 500); lo = [B * 0.05 / n] * n; hi = [B * 0.6] * n
        cv = Conveyance(n, B, rho=0.8)
        for t in range(30):
            a = cv.step([rng.uniform(0, B * 0.5) for _ in range(n)], lo, hi)
            assert sum(a) <= B * (1 + 1e-9) and all(x >= l - 1e-9 for x, l in zip(a, lo)), (a, B)
    print("PASS test_conveyance: conservation, Lyapunov ascent, exact exponential convergence, projection bounds, budget never exceeded")


if __name__ == "__main__":
    main()
