"""Site power exchange: G GPU groups share one site power budget (power oversubscription: the budget is below the sum
of TDPs). THEORETICAL SIMULATION on the device physics of hardware/plant.py (MLPerf-calibrated gamma).

Each group has its own demand (different traffic shapes and phases). Settings are GPU power-limit fractions s; group
capacity = n s^gamma; power per device = p_idle + (s p_max - p_idle) u.

Arms, all under the same site budget, all with the same site breaker (if a step's site power exceeds the budget, the
next step every group is throttled uniformly to fit, which is how a reactive site capper behaves):
  A  native: every GPU at TDP; only the reactive site capper
  S  static split: every group gets budget / G (the common manual practice)
  I  independent: each group sized by the device law (want / rho)^(1/gamma) on its own, no exchange
  X  conveyance: the conserved-budget replicator flow of omnicompass/conveyance.py moves watts between groups toward
     need, holds a reserve for projected rises, releases it continuously (manuscript Ch. 29-31)

Gauges: work served, backlog (SLO breach) minutes, p95 latency factor, energy, site-budget violation minutes, peak.
Usage: python hardware/site_exchange.py [--scenarios 24] [--seed 818181] [--budget 0.7]"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hardware.plant import VESSELS, FAMILIES, demand_trace
from omnicompass.conveyance import Conveyance

G, N = 4, 16      # 4 groups x 16 GPUs


def run(v, fams, seed, arm, budget_frac, steps=360, rho=0.8):
    rng = np.random.default_rng(seed)
    dem = [demand_trace(f, steps, np.random.default_rng(seed + 97 * k)) for k, f in enumerate(fams)]
    shift = [int(rng.integers(0, steps)) for _ in range(G)]
    dem = [np.roll(d, sh) for d, sh in zip(dem, shift)]
    budget = budget_frac * G * N * v.p_max
    backlog = [0.0] * G; s = [1.0] * G; throttle = 1.0
    cv = Conveyance(G, budget, rho=rho)
    energy = work = peak = 0.0; slo = viol = 0; lat = []
    for t in range(steps):
        want = [dem[k][t] + backlog[k] for k in range(G)]
        if arm == "A":
            s = [1.0] * G
        elif arm == "S":
            s = [min(1.0, budget / G / (N * v.p_max))] * G
        elif arm == "I":
            s = [max(v.f_min, min(1.0, (w / rho) ** (1.0 / v.gamma))) for w in want]
        else:
            need_w = [N * v.p_max * max(v.f_min, min(1.0, (w / rho) ** (1.0 / v.gamma))) * rho for w in want]
            a = cv.step(need_w, [N * v.p_max * v.f_min] * G, [N * v.p_max] * G)
            s = [max(v.f_min, min(1.0, ak / (N * v.p_max))) for ak in a]
        s = [max(v.f_min, x * throttle) for x in s]
        power = 0.0; srv_all = 0.0
        for k in range(G):
            cap = s[k] ** v.gamma
            served = min(want[k], cap); u = served / max(cap, 1e-9)
            power += N * (v.p_idle + (s[k] * v.p_max - v.p_idle) * u)
            backlog[k] = max(0.0, want[k] - served); srv_all += served
            slo += int(backlog[k] > dem[k][t]); lat.append(1.0 + backlog[k] / max(dem[k][t], 1e-3))
        energy += power / 60.0 / 1000.0; work += srv_all; peak = max(peak, power)
        over = power > budget * 1.0001
        viol += int(over)
        # reactive site breaker: throttle next step uniformly to fit the budget, relax slowly when under it
        throttle = min(1.0, throttle * budget / power) if over else min(1.0, throttle * 1.02)
    return {"work": work, "backlog_min": float(slo), "p95_latency_x": float(np.percentile(lat, 95)), "energy_kwh": energy,
            "site_violation_min": float(viol), "peak_kw": peak / 1000.0}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--scenarios", type=int, default=24); ap.add_argument("--seed", type=int, default=818181)
    ap.add_argument("--budget", type=float, default=0.7); ap.add_argument("--out", default="results/hardware/SITE_EXCHANGE.json")
    a = ap.parse_args(argv)
    v = VESSELS["gpu_mlperf_median"]; rng = np.random.default_rng(a.seed)
    scen = [([FAMILIES[int(rng.integers(0, len(FAMILIES)))] for _ in range(G)], int(rng.integers(1, 2**31))) for _ in range(a.scenarios)]
    rows = {arm: [run(v, f, s, arm, a.budget) for f, s in scen] for arm in ("A", "S", "I", "X")}
    keys = list(rows["A"][0]); br = np.random.default_rng(7)
    out = {"note": "THEORETICAL SIMULATION; hardware/site_exchange.py", "seed": a.seed, "scenarios": a.scenarios, "budget_frac": a.budget,
           "means": {k: {m: float(np.mean([r[m] for r in rows[k]])) for m in keys} for k in rows}, "paired_X_vs": {}}
    for base in ("A", "S", "I"):
        out["paired_X_vs"][base] = {}
        for m in keys:
            d = np.array([rows["X"][i][m] - rows[base][i][m] for i in range(len(scen))])
            bs = d[br.integers(0, len(d), (4000, len(d)))].mean(1); lo, hi = np.percentile(bs, [2.5, 97.5])
            out["paired_X_vs"][base][m] = {"delta": float(d.mean()), "ci95": [float(lo), float(hi)], "significant": bool(lo > 0 or hi < 0)}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"site budget {a.budget:.0%} of TDP, {a.scenarios} scenarios, seed {a.seed}")
    print(f"{'gauge':20s}" + "".join(f"{x:>11s}" for x in ("A native", "S static", "I indep.", "X convey")))
    for m in keys:
        print(f"{m:20s}" + "".join(f"{out['means'][k][m]:11.3f}" for k in ("A", "S", "I", "X")))
    for base in ("A", "S", "I"):
        sig = {m: round(v_['delta'], 3) for m, v_ in out["paired_X_vs"][base].items() if v_["significant"]}
        print(f"X vs {base}, significant:", sig)


if __name__ == "__main__":
    main()
