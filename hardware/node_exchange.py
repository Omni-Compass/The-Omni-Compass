"""CPU and GPU on one conserved power budget: the conveyance law (omnicompass/conveyance.py) with CPU organs beside
GPU organs, so watts a CPU holds and does not need flow to the GPUs that need them. THEORETICAL SIMULATION on the
device physics of hardware/plant.py (GPU gamma fitted to MLPerf v4.0 DGX-H100 MaxQ vs MaxP; CPU first-order DVFS).

The law, read as mechanism (docs/CONVEYANCE_LAW.md): the site's watts are conserved (moved between organs, never
created, Ch. 29 §8); they flow down the gradient of need, from organs holding surplus to organs in deficit (Ch. 31 §4);
the flow converges (Re(lambda) < 0, Ch. 31 §5); a reserve for the projected rise is released continuously (Ch. 30).
Here the organs are G GPU groups and the G CPU groups that feed them.

A group = N GPUs and M CPU sockets (two 8-GPU servers: 16 H100-class GPUs, 4 sockets).
  GPU   capacity s^gamma at power-limit fraction s; power per device p_idle + (s p_max - p_idle) u
  CPU   capacity f at clock fraction f; power per socket p_idle + (p_max - p_idle) u f^3; clock set by a ceiling
        (cpufreq scaling_max_freq or a RAPL package limit, the hardware connectors in omni_controller/muscles.py)
  work  the GPUs serve requests; each unit of GPU work needs --cpu-share of the CPUs at full clock to feed it:
        served = min(demand + backlog, GPU capacity, CPU capacity / cpu-share)
  site  one budget = --budget x (sum of GPU TDP + sum of CPU maximum power); a reactive breaker throttles every
        device uniformly the step after the site draws over it (how a site power capper behaves)

Arms, same demand, same budget, same breaker:
  A   native: GPUs at TDP, CPUs on their own governor (schedutil-style), only the breaker (it trips: a real
      power-limited site cannot run this way)
  S   today's practice: every GPU capped at one fixed limit low enough that the site fits even with every CPU at its
      maximum, (budget - CPU maximum) / GPU TDP; CPUs on their own governor
  XR  conveyance among the GPU groups; the CPUs are uncontrolled, so their full maximum power stays reserved
      (the planning rule when nothing holds the CPUs down); GPU budget = site budget - CPU maximum
  XM  conveyance among the GPU groups; GPU budget = site budget - the CPUs' measured draw, updated every step
  XC  conveyance over CPU and GPU organs together: each CPU group is held to the clock its feeding work needs, and
      the watts it no longer holds flow to the GPU groups with the largest deficit

Gauges: work served (GPU work units), backlog minutes (SLO breach), p95 latency factor, energy, work per kWh,
site-budget violation minutes, peak. Usage: python hardware/node_exchange.py [--scenarios 24] [--budget 0.7] [--load 1.3]
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hardware.plant import VESSELS, FAMILIES, demand_trace
from omnicompass.conveyance import Conveyance

G, N, M = 4, 16, 4
CPU_IDLE, CPU_MAX, CPU_FMIN = 120.0, 400.0, 0.4      # per socket, the cpu vessel of hardware/plant.py
ARMS = ("A", "S", "XR", "XM", "XC")


def cpu_power(f, load):
    """Group CPU power at clock f serving load (share of the group's CPU at full clock): busy fraction load / f."""
    u = min(1.0, load / max(f, 1e-9))
    return M * (CPU_IDLE + (CPU_MAX - CPU_IDLE) * u * f ** 3)


def cpu_clock_for(watts, load):
    """The highest clock whose group power at this load fits the allocation (power = idle + dyn load f^2 while u < 1)."""
    dyn = (CPU_MAX - CPU_IDLE) * max(load, 1e-6)
    f = math.sqrt(max(0.0, (watts / M - CPU_IDLE) / dyn))
    return max(CPU_FMIN, min(1.0, f))


def gpu_need(v, want, rho):
    s = max(v.f_min, min(1.0, (want / rho) ** (1.0 / v.gamma)))
    return N * (v.p_idle + (s * v.p_max - v.p_idle) * rho), s


def cpu_need(want, c, rho):
    f = max(CPU_FMIN, min(1.0, c * want / rho))
    return cpu_power(f, min(c * want, f)) , f


def run(v, fams, seed, arm, budget_frac, c=0.35, load=1.3, steps=360, rho=0.8):
    rng = np.random.default_rng(seed)
    dem = [load * demand_trace(f, steps, np.random.default_rng(seed + 97 * k)) for k, f in enumerate(fams)]
    shift = [int(rng.integers(0, steps)) for _ in range(G)]
    dem = [np.roll(d, sh) for d, sh in zip(dem, shift)]
    gpu_tdp, cpu_top = G * N * v.p_max, G * M * CPU_MAX
    budget = budget_frac * (gpu_tdp + cpu_top)
    backlog = [0.0] * G; throttle = 1.0; last_cpu = G * M * CPU_IDLE
    cv_gpu = Conveyance(G, max(1.0, budget - cpu_top), rho=rho)
    cv_all = Conveyance(2 * G, budget, rho=rho)
    energy = work = peak = 0.0; slo = viol = 0; lat = []
    lo_g, hi_g = [N * v.p_max * v.f_min] * G, [N * v.p_max] * G
    lo_c, hi_c = [M * CPU_IDLE * 1.05] * G, [M * CPU_MAX] * G
    for t in range(steps):
        want = [dem[k][t] + backlog[k] for k in range(G)]
        f = [max(CPU_FMIN, min(1.0, 1.25 * c * w)) for w in want]          # the CPUs' own governor
        if arm == "A":
            s = [1.0] * G
        elif arm == "S":
            s = [max(v.f_min, min(1.0, (budget - cpu_top) / gpu_tdp))] * G
        elif arm in ("XR", "XM"):
            cv_gpu.budget = max(sum(lo_g), budget - (cpu_top if arm == "XR" else last_cpu))
            a = cv_gpu.step([gpu_need(v, w, rho)[0] for w in want], lo_g, hi_g)
            s = [max(v.f_min, min(1.0, ak / (N * v.p_max))) for ak in a]
        else:
            need = [gpu_need(v, w, rho)[0] for w in want] + [cpu_need(w, c, rho)[0] for w in want]
            a = cv_all.step(need, lo_g + lo_c, hi_g + hi_c)
            s = [max(v.f_min, min(1.0, ak / (N * v.p_max))) for ak in a[:G]]
            f = [min(fk, cpu_clock_for(ak, c * min(w, 1.3))) for fk, ak, w in zip(f, a[G:], want)]
        s = [max(v.f_min, x * throttle) for x in s]
        f = [max(CPU_FMIN, x * throttle) for x in f]
        power = 0.0; cpu_w = 0.0; served_all = 0.0
        for k in range(G):
            gcap = s[k] ** v.gamma
            served = min(want[k], gcap, f[k] / c)
            u = served / max(gcap, 1e-9)
            pc = cpu_power(f[k], c * served)
            power += N * (v.p_idle + (s[k] * v.p_max - v.p_idle) * u) + pc; cpu_w += pc
            backlog[k] = max(0.0, want[k] - served); served_all += served
            slo += int(backlog[k] > dem[k][t]); lat.append(1.0 + backlog[k] / max(dem[k][t], 1e-3))
        last_cpu = cpu_w
        energy += power / 60.0 / 1000.0; work += served_all; peak = max(peak, power)
        over = power > budget * 1.0001
        viol += int(over)
        throttle = min(1.0, throttle * budget / power) if over else min(1.0, throttle * 1.02)
    return {"work": work, "backlog_min": float(slo), "p95_latency_x": float(np.percentile(lat, 95)),
            "energy_kwh": energy, "work_per_kwh": work / max(energy, 1e-9), "site_violation_min": float(viol),
            "peak_kw": peak / 1000.0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=24); ap.add_argument("--seed", type=int, default=515151)
    ap.add_argument("--budget", type=float, default=0.7, help="site budget as a share of GPU TDP + CPU maximum")
    ap.add_argument("--load", type=float, default=1.3, help="demand multiplier on hardware/plant.py's traces")
    ap.add_argument("--cpu-share", type=float, default=0.35, help="CPU at full clock needed per unit of GPU work")
    ap.add_argument("--vessel", default="gpu_mlperf_median")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    v = VESSELS[a.vessel]; rng = np.random.default_rng(a.seed)
    scen = [([FAMILIES[int(rng.integers(0, len(FAMILIES)))] for _ in range(G)], int(rng.integers(1, 2**31))) for _ in range(a.scenarios)]
    rows = {arm: [run(v, fm, sd, arm, a.budget, a.cpu_share, a.load) for fm, sd in scen] for arm in ARMS}
    keys = list(rows["A"][0]); br = np.random.default_rng(7)
    out = {"note": "THEORETICAL SIMULATION; hardware/node_exchange.py", "args": vars(a), "gamma": v.gamma,
           "means": {k: {m: float(np.mean([r[m] for r in rows[k]])) for m in keys} for k in rows}, "paired_XC_vs": {}}
    for base in ("A", "S", "XR", "XM"):
        out["paired_XC_vs"][base] = {}
        for m in keys:
            d = np.array([rows["XC"][i][m] - rows[base][i][m] for i in range(len(scen))])
            bs = d[br.integers(0, len(d), (4000, len(d)))].mean(1); lo, hi = np.percentile(bs, [2.5, 97.5])
            ref = float(np.mean([r[m] for r in rows[base]]))
            out["paired_XC_vs"][base][m] = {"delta": float(d.mean()), "pct": 100 * float(d.mean()) / ref if ref else None,
                                            "ci95": [float(lo), float(hi)], "significant": bool(lo > 0 or hi < 0)}
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"site budget {a.budget:.0%} of GPU TDP + CPU max, load x{a.load}, CPU share {a.cpu_share}, gamma {v.gamma:.2f}, "
          f"{a.scenarios} scenarios")
    print(f"{'gauge':20s}" + "".join(f"{x:>11s}" for x in ("A native", "S static", "XR gpu+res", "XM gpu+meas", "XC cpu+gpu")))
    for m in keys:
        print(f"{m:20s}" + "".join(f"{out['means'][k][m]:11.3f}" for k in ARMS))
    for base in ("A", "S", "XR", "XM"):
        sig = {m: f"{x['pct']:+.1f}%" for m, x in out["paired_XC_vs"][base].items() if x["significant"] and x["pct"] is not None}
        print(f"XC vs {base}, significant:", sig)
    return out


if __name__ == "__main__":
    main()
