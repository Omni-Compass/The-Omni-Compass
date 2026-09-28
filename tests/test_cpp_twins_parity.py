"""C++ twins (cpp/src/nervous_system.cpp, compass.cpp, gpu_rules.cpp) vs their Python originals
(omnicompass/nervous_system.py, omnicompass/compass.py with omnicompass/storage.py, and the pure rules of
omni_controller/gpu_governor.py) on random inputs: the same authority, gate, compass reading, ledger, GPU limit, busy
gate, speed-lock step, response-time window and baseline, value for value.
Usage: python tests/test_cpp_twins_parity.py OC_TWINS [cases]"""
import math, random, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.nervous_system import NervousInputs, authority, node_release_gate
from omnicompass.closure import stress_equilibrium
from omnicompass.compass import Compass
from omnicompass.core import State, Params
from omni_controller.gpu_governor import shield_limit, busy_gate, lock_decide, baseline_at, window_stats


def run(exe, mode, lines, d):
    fin, fout = d / f"{mode}.in", d / f"{mode}.out"
    fin.write_text("".join(",".join(repr(float(x)) if not isinstance(x, str) else x for x in l) + "\n" for l in lines))
    subprocess.run([exe, mode, str(fin), str(fout)], check=True)
    return [l.split(",") for l in fout.read_text().splitlines()]


def same(a, b, what):
    fa = float(a)
    assert fa == b or (math.isinf(fa) and math.isinf(b)), f"{what}: C++ {a} vs Python {b!r}"


def nervous(exe, rng, n, d):
    rows = []
    for _ in range(n):
        rows.append([rng.uniform(-2, 2), rng.uniform(-1.5, 1.5), rng.uniform(-1, 2), rng.uniform(0, 3), rng.uniform(0, 1),
                     rng.choice([0.2, 0.1, 0.35]), rng.choice([0.5, 0.3, 0.7]), rng.uniform(0.5, 3), rng.choice([0, 0, 0, 1]),
                     rng.choice([1, 1, 0]), rng.uniform(0, 1.1), rng.uniform(0.3, 1.2), rng.choice([0, 0, 1]),
                     rng.choice([0, 0, 0, 0.5]), rng.choice([1, 1, 0]), rng.choice([0] * 9 + [1])])
    out = run(exe, "nervous", rows, d)
    for r, c in zip(rows, out):
        i = NervousInputs(E=r[0], U=r[1], I_U=r[2], S=r[3], push=r[4], push_release=r[5], U_gate=r[6], s_eq=r[7],
                          security_block=r[8], slo_clean=bool(r[9]), power_stress=r[10], thermal=r[11], rollback=bool(r[12]),
                          stale=r[13], mode="autopilot" if r[14] else "observe", killed=bool(r[15]))
        a = authority(i); py = [float(a["execute"]), float(a["killed"])]
        if not a["killed"]:
            sc = a["scalars"]; org = a["organs"]
            py += [float(a["security_hold"]), sc["kappa"], sc["h"], sc["sigma"], sc["nu"], sc["calm"]]
            for o in ("pods", "nodes", "cpufreq", "gpu", "power", "routing"):
                py += [float(org[o]["expand"]), float(org[o]["contract"]), org[o]["step"]]
            for o in ("cpufreq", "gpu", "power", "routing"):
                py += list(org[o]["envelope"])
            py += [float(org["cooling"]["contract"]), org["cooling"]["step"]] + list(org["cooling"]["envelope"])
            py += [float(org["batch"]["admit"]), float(org["batch"]["pause"]), float(org["rollback"]["authorized"])]
            py += [stress_equilibrium(r[3] + 0.5, 0.12, 0.10)]
        assert len(py) == len(c), (len(py), len(c))
        for k, (x, y) in enumerate(zip(c, py)):
            same(x, y, f"nervous field {k}")
    rows = [[rng.randint(0, 8), rng.uniform(1000, 8000), rng.uniform(0, 30000), rng.choice([0, 0, 1]), rng.choice([0, 0, 1]),
             rng.choice([0, 0, 1]), rng.uniform(0.5, 0.95), rng.choice([1, 1, 0]), rng.choice([1, 1, 0]), rng.choice([1, 1, 0])] for _ in range(n)]
    for r, c in zip(rows, run(exe, "gate", rows, d)):
        g = node_release_gate(int(r[0]), r[1], r[2], int(r[3]), bool(r[4]), bool(r[5]), r[6], {"organs": {"nodes": {"contract": bool(r[7])}}},
                              senses_live=bool(r[8]), last_command_landed=bool(r[9]))
        same(c[0], float(g["ok"]), "gate ok"); same(c[1], g["util_after"], "gate util_after")


def compass(exe, rng, n, d):
    for use_state in (0, 1):
        hdr = [rng.uniform(0.5, 2), rng.uniform(0.05, 0.3), rng.uniform(0.02, 0.2), rng.uniform(0.2, 0.8), use_state]
        c = Compass(E_max=hdr[0], alpha_s=hdr[1], beta_s=hdr[2], delta=hdr[3])
        rows, E = [], 0.0
        for t in range(n):
            E += rng.uniform(-0.3, 0.3)
            r = [E, rng.uniform(0, 3), rng.uniform(0, 1), rng.uniform(-0.1, 0.1), rng.uniform(0, 1), rng.uniform(-0.1, 0.1), rng.choice([0, 1])]
            if use_state:
                r += [E, rng.uniform(-1.5, 1.5), rng.uniform(-1, 1), rng.uniform(0, 3), rng.uniform(-1, 1), rng.uniform(-1, 1),
                      rng.uniform(0.05, 0.3), rng.uniform(0.02, 0.2), rng.uniform(0.2, 0.8), rng.uniform(0.5, 3), rng.uniform(0.5, 5),
                      rng.uniform(0.1, 1), rng.uniform(0.5, 2), rng.uniform(0.5, 2), rng.uniform(0.2, 2)]
            rows.append(r)
        out = run(exe, "compass", [hdr] + rows, d)
        for r, o in zip(rows, out):
            x = p = None
            if use_state:
                x = State(E=r[7], U=r[8], I_U=r[9], S=r[10], B=r[11], B_dot=r[12])
                p = Params(alpha_s=r[13], beta_s=r[14], delta=r[15], omega_B=r[16], Q_B=r[17], gamma_c=r[18], mu=r[19], alpha_E=r[20], lambda_I=r[21])
            py = c.read(r[0], r[1], {"a": r[2], "b": r[4]}, {"a": r[3], "b": r[5]}, forced=bool(r[6]), x=x, p=p)
            v = [float(z) for z in o]
            assert round(v[0], 1) == py["heading_deg"] and round(v[4], 4) == py["e"] and round(v[5], 3) == py["rate"], (v, py)
            assert round(v[6], 4) == py["axle_rest"] and round(v[7], 5) == py["ledger"], (v, py)
            assert (py["ledger_step"] is None) == (v[8] == 0) and (py["ledger_step"] is None or round(v[9], 5) == py["ledger_step"]), (v, py)
            from omnicompass.compass import RIM, POINTS
            assert RIM[int(v[1])] == py["letter"] and POINTS[int(v[2])][0] == py["point"] and int(v[3]) == py["quadrant"], (v, py)
            assert (py["descent"] is None and v[10] == 0) or bool(v[10]) == py["descent"], (v, py)
            assert bool(v[11]) == py["omega_held"] and bool(v[12]) == py["inward"] and int(v[13]) == py["circles_closed"], (v, py)


def gpu(exe, rng, n, d):
    rows = [[rng.uniform(0.3, 1.2), rng.uniform(20, 700), rng.choice([300.0, 350.0, 700.0]), rng.choice([100.0, 150.0]),
             rng.choice([0.3, 0.1]), rng.choice([0.0, 0.7, 0.75]), rng.choice([1, 1, 0])] for _ in range(n)]
    for r, c in zip(rows, run(exe, "shield", rows, d)):
        w, b = shield_limit(*r[:6], bool(r[6]))
        assert int(float(c[0])) == w and c[1] == b, (r, c, w, b)
    rows = [[rng.uniform(0, 1), 0.5, 0.1] for _ in range(n)]
    u, gated = None, False
    for r, c in zip(rows, run(exe, "busy", rows, d)):
        u, gated = busy_gate(u, r[0], gated, r[1], r[2])
        same(c[0], u, "busy u"); same(c[1], float(gated), "busy gated")
    rows = [[rng.uniform(0.3, 1.2), rng.uniform(150, 300), 300.0, 100.0, rng.choice([0.0, 5.0, 20.0]), 0.01, rng.choice([0.02, 0.08]),
             0.02, 5.0, 0.5, 10.0] for _ in range(n)]
    for r, c in zip(rows, run(exe, "lock", rows, d)):
        w, b, line, aim = lock_decide(*r)
        assert int(float(c[0])) == w and c[1] == b, (r, c, w, b)
        same(c[2], line, "lock line"); same(c[3], aim, "lock aim")
    lat = d / "lat.csv"
    for _ in range(20):
        w = rng.choice([30.0, 60.0]); m = rng.randint(5, 400)
        pts = sorted((rng.uniform(0, 120), rng.uniform(10, 900), rng.choice([1, 1, 1, 0])) for _ in range(m))
        lat.write_text("elapsed_seconds,latency_ms,ok\n" + "".join(f"{t!r},{ms!r},{ok}\n" for t, ms, ok in pts))
        py = window_stats(str(lat), w)
        c = run(exe, "window", [[w]] + [list(p) for p in pts], d)[0]
        if py is None:
            assert c == ["none"], c
        else:
            for k, key in enumerate(("mean", "p95", "p99", "rate", "n")):
                same(c[k], float(py[key]), f"window {key}")
    bins = sorted(({"rate": rng.uniform(1, 20), "mean": rng.uniform(50, 200), "p95": rng.uniform(200, 400), "p99": rng.uniform(400, 800)}
                   for _ in range(6)), key=lambda b: b["rate"])
    rates = [[rng.uniform(0, 22)] for _ in range(n)]
    out = run(exe, "baseline", [[len(bins)]] + [[b["rate"], b["mean"], b["p95"], b["p99"]] for b in bins] + rates, d)
    for r, c in zip(rates, out):
        py = baseline_at({"bins": bins}, r[0])
        for k, key in enumerate(("mean", "p95", "p99")):
            same(c[k], py[key], f"baseline {key}")


def main(exe, cases=2000):
    rng = random.Random(20260929); d = Path(tempfile.mkdtemp())
    nervous(exe, rng, cases, d); compass(exe, rng, cases // 4, d); gpu(exe, rng, cases, d)
    print(f"PASS test_cpp_twins_parity: nervous system ({cases} authorities, {cases} release gates), compass and ledger "
          f"({cases // 2} readings, with and without the engine state), GPU rules ({cases} limits, busy gates, lock steps; "
          f"windows; baselines): C++ equals Python value for value")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2000)
