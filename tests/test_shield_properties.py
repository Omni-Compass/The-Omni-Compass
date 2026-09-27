"""Property test of the safety shield over a large random and adversarial input space.

For every generated (action set, state, observation, bounds, limits):
  P1  the enforced action set violates no invariant I1-I5            violations(enforce(x)) == []
  P2  enforcement is idempotent                                      enforce(enforce(x)) == enforce(x), 0 new hits
  P3  enforcement never invents an action                            every output action kind was in the input
  P4  a clean action set passes unchanged with no intervention       violations(x) == [] -> enforce(x) == (x, 0)
The generator mixes uniform draws with adversarial corners: node targets far outside the bounds, current node counts
outside the bounds, power stress at and beyond the limit, security holds, caps outside [0.65, 1], contradictory sets
(expand and tighten together), zero and negative targets. Usage: python tests/test_shield_properties.py [cases]"""
import random, sys
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.shield import enforce, violations, ShieldLimits

KINDS = ["nodes", "power_cap", "terraform_plan", "rollout", "replicas"]


def case(rng):
    lo = rng.choice([0, 1, 1, 2, 3, 5]); hi = lo + rng.choice([0, 1, 5, 20, 100])
    n = rng.choice([0, 1, lo, hi, rng.randint(0, 150), hi + rng.randint(1, 10), max(0, lo - rng.randint(1, 5))])
    st = {"actual_nodes": n, "power_cap": rng.choice([0.65, 0.8, 1.0, rng.uniform(0.5, 1.2)])}
    obs = {"power_stress": rng.choice([0.0, 0.5, 0.99, 1.0, 1.01, 2.0, rng.uniform(0, 3)]),
           "security_block": rng.choice([0.0, 0.0, 1.0, rng.random()])}
    acts = []
    for _ in range(rng.randint(0, 4)):
        k = rng.choice(KINDS)
        if k == "nodes":
            t = rng.choice([-5, 0, lo, hi, n, n + 1, n - 1, n + 50, rng.randint(-10, 300)])
            acts.append({"action": k, "target": t, "direction": 1 if t > max(1, n) else -1})
        elif k == "power_cap":
            c = rng.choice([0.0, 0.3, 0.65, 0.7, 1.0, 1.5, rng.uniform(-1, 2)])
            acts.append({"action": k, "target": c, "direction": -1 if c < st["power_cap"] else 1})
        else:
            acts.append({"action": k, "target": 1, "direction": rng.choice([-1, 1])})
    lim = ShieldLimits(power_limit=rng.choice([1.0, 1.05, 0.9, 1e9]), max_node_step=rng.choice([1, 2, 4, 10]))
    return acts, st, obs, SimpleNamespace(minimum_nodes=lo, maximum_nodes=hi), lim


def main(n_cases=2_000_000):
    rng = random.Random(20260927)
    bad = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}; first = {}
    for i in range(n_cases):
        acts, st, obs, cfg, lim = case(rng)
        out, hits = enforce(acts, st, obs, cfg, lim)
        checks = {"P1": not violations(out, st, obs, cfg, lim)}
        out2, hits2 = enforce(out, st, obs, cfg, lim)
        checks["P2"] = out2 == out and hits2 == 0
        checks["P3"] = all(any(a["action"] == b["action"] for b in acts) for a in out)
        if not violations(acts, st, obs, cfg, lim):
            checks["P4"] = hits == 0 and len(out) == len([a for a in acts if not (a["action"] == "nodes" and int(a["target"]) == max(1, int(st["actual_nodes"])))])
        for k, ok in checks.items():
            if not ok:
                bad[k] += 1; first.setdefault(k, (acts, st, obs, vars(cfg), lim, out))
    print(f"shield properties over {n_cases:,} cases:", bad)
    for k, v in first.items():
        print("first counterexample", k, v)
    assert not any(bad.values()), bad
    print("PASS test_shield_properties")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000)
