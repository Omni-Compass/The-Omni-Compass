"""Device plant: CPU frequency (DVFS) and GPU power-limit muscles, three architectures, 24 scenarios.

SIMULATION. CPU physics use a standard first-order model with declared constants. The GPU performance-vs-power-limit
exponent gamma is fitted to real metered hardware: MLPerf Inference v4.0 NVIDIA DGX-H100 MaxQ vs MaxP
(results/hardware/CALIBRATION_MLPERF.json, Apache 2.0); the median, least favourable and most favourable fits are all
run. Replace with measured curves (RAPL, nvidia-smi) when the hardware connectors in omni_controller/muscles.py run on
owned machines.

Physics (per device, one step = 60 s)
  CPU   power = P_idle + P_dyn * u * f^3          (dynamic power ~ C V^2 f with V ~ f)
        capacity = f                               (compute-bound work scales with clock)
  GPU   power = P_idle + (L - P_idle) * u          (the board draws up to its power limit L when busy)
        capacity = (L / TDP)^gamma                 (concave performance-vs-power-limit curve, gamma per workload)
  Queue backlog += demand - served; SLO breach when backlog exceeds one step of demand.
  Heat  thermal = 0.86 thermal + 0.14 (0.34 + 0.62 power_stress)   (the harness heat law)

Architectures (the only difference between arms is who sets f or L)
  A  native      CPU: schedutil-style governor f = min(1, 1.25 u_needed); GPU: power limit = TDP (vendor default)
  B  on top      the native governor runs, Omni-Compass sets a ceiling: f = min(native f, cap); L = cap x TDP
  C  direct      Omni-Compass replaces the native governor. CPU: f = min(cap, want / rho*), rho* the engine's target
                 utilisation (its demand output), floor f_min; GPU: L = cap x TDP (floor f_min)
  S  reference   a fixed manual cap at 70% (f or L), no Omni-Compass: what an operator could do by hand
Omni-Compass = the shipped Governor (fleet law); its power_cap output is the cap.
"""
from __future__ import annotations

import argparse, json, math, sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass.adapter import Governor, mode_law, AUTOPILOT


@dataclass
class Vessel:
    name: str
    devices: int
    p_idle: float        # W per device
    p_max: float         # W per device at full load, full clock / TDP
    gamma: float         # GPU perf-vs-power exponent (unused for CPU)
    kind: str            # "cpu" or "gpu"
    f_min: float = 0.4   # lowest clock or power-limit fraction the device allows


_CAL = json.loads((ROOT / "results/hardware/CALIBRATION_MLPERF.json").read_text())
VESSELS = {
    "cpu_web": Vessel("cpu_web", 100, 120.0, 400.0, 0.0, "cpu"),
    # H100-class GPUs, TDP 700 W; gamma measured from MLPerf v4.0 MaxQ vs MaxP (results/hardware/CALIBRATION_MLPERF.json).
    # Floor 300 W / 700 W = 0.43, the lowest limit NVIDIA used for MaxQ.
    "gpu_mlperf_median": Vessel("gpu_mlperf_median", 64, 60.0, 700.0, _CAL["gamma_median"], "gpu", 300 / 700),
    "gpu_mlperf_least_favourable": Vessel("gpu_mlperf_least_favourable", 64, 60.0, 700.0, _CAL["gamma_max"], "gpu", 300 / 700),
    "gpu_mlperf_most_favourable": Vessel("gpu_mlperf_most_favourable", 64, 60.0, 700.0, _CAL["gamma_min"], "gpu", 300 / 700),
}
FAMILIES = ["steady", "diurnal", "spike", "flash_crowd", "slow_ramp", "lull", "burst_train", "mixed"]


def demand_trace(family, steps, rng):
    t = np.arange(steps)
    base = {"steady": 0.55, "diurnal": 0.5, "spike": 0.45, "flash_crowd": 0.4, "slow_ramp": 0.3, "lull": 0.25,
            "burst_train": 0.5, "mixed": 0.5}[family]
    d = np.full(steps, base)
    if family == "diurnal":
        d = 0.5 + 0.3 * np.sin(2 * math.pi * t / steps)
    elif family == "spike":
        d[steps // 3: steps // 3 + 20] = 0.95
    elif family == "flash_crowd":
        d[steps // 2: steps // 2 + 8] = 1.1
    elif family == "slow_ramp":
        d = 0.25 + 0.6 * t / steps
    elif family == "burst_train":
        d = np.where((t // 30) % 2 == 0, 0.85, 0.3)
    elif family == "mixed":
        d = 0.5 + 0.25 * np.sin(2 * math.pi * t / (steps / 3)) + np.where((t // 45) % 4 == 0, 0.25, 0.0)
    return np.clip(d * (1 + 0.06 * rng.standard_normal(steps)), 0.05, 1.3)


def device(v, setting, u):
    """power per device (W) and capacity fraction at setting (clock or power-limit fraction) and busy fraction u."""
    if v.kind == "cpu":
        return v.p_idle + (v.p_max - v.p_idle) * u * setting ** 3, setting
    cap_w = setting * v.p_max
    return v.p_idle + (cap_w - v.p_idle) * u, setting ** v.gamma


def run(v, family, seed, arm, steps=360):
    rng = np.random.default_rng(seed)
    dem = demand_trace(family, steps, rng)
    g = Governor(law=mode_law("fleet")); g.set_mode(AUTOPILOT); g.nodes = v.devices
    site = v.devices * v.p_max
    backlog = energy = work = peak = 0.0
    thermal, cap, rho = 0.32, 1.0, 0.8
    slo = heat_v = power_v = 0
    lat = []
    settings = []
    for i in range(steps):
        want = dem[i] + backlog                           # fraction of full fleet capacity wanted this step
        if v.kind == "cpu":
            native = min(1.0, max(v.f_min, 1.25 * want))  # schedutil-style frequency choice
        else:
            native = 1.0                                  # vendor default power limit = TDP
        if arm == "A":
            s = native
        elif arm == "S":
            s = max(v.f_min, min(native, 0.7))            # static manual cap at 70% (common operator practice)
        elif arm == "B":
            s = native if backlog > 0.05 * dem[i] else min(native, max(v.f_min, cap))   # release on backlog
        elif backlog > 0.05 * dem[i]:
            s = 1.0                                       # release on backlog (the engine's guard_queue rule)
        elif v.kind == "cpu":
            s = min(max(v.f_min, cap), max(v.f_min, min(1.0, want / max(rho, 1e-3))))
        else:
            s = max(v.f_min, cap)
        pw1, capf = device(v, s, 1.0)
        served = min(want, capf)
        u = served / max(capf, 1e-9)
        pw, _ = device(v, s, u)
        backlog = max(0.0, want - served)
        power = v.devices * pw
        energy += power / 60.0 / 1000.0                  # kWh (60 s step)
        work += served
        peak = max(peak, power)
        stress = power / site
        thermal = min(1.35, max(0.0, 0.86 * thermal + 0.14 * (0.34 + 0.62 * min(1.35, stress))))
        slo += int(backlog > dem[i])
        heat_v += int(thermal > 1.03 * 0.82)
        power_v += int(stress > 0.95)
        lat.append(1.0 + backlog / max(dem[i], 1e-3))
        settings.append(s)
        if arm in ("B", "C"):
            obs = {"queue_ratio": min(2.0, backlog / max(dem[i], 1e-3)), "load_ratio": min(2.0, want),
                   "power_stress": stress, "thermal": thermal, "network_stress": 0.0, "drift_ratio": 0.0, "stale": 0.0,
                   "security_block": 0.0}
            g.current_cap = cap
            d = g.step(obs, 0)
            cap = float(d["power_cap"]); rho = float(d["demand"])
    lat = np.array(lat)
    return {"energy_kwh": energy, "work": work, "kwh_per_work": energy / max(work, 1e-9), "peak_kw": peak / 1000.0,
            "slo_breach_min": float(slo), "p95_latency_x": float(np.percentile(lat, 95)), "mean_latency_x": float(lat.mean()),
            "heat_over_min": float(heat_v), "power_over_min": float(power_v), "mean_setting": float(np.mean(settings)),
            "setting_changes": float(np.sum(np.abs(np.diff(settings)) > 0.01))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", type=int, default=24); ap.add_argument("--seed", type=int, default=515151)
    ap.add_argument("--out", default="results/hardware/SUMMARY.json")
    a = ap.parse_args(argv)
    out = {"note": "THEORETICAL SIMULATION of device physics; constants declared in hardware/plant.py", "seed": a.seed,
           "scenarios": a.scenarios, "vessels": {}}
    rng = np.random.default_rng(a.seed)
    scen = [(FAMILIES[i % len(FAMILIES)], int(rng.integers(1, 2**31))) for i in range(a.scenarios)]
    for vn, v in VESSELS.items():
        rows = {arm: [run(v, f, s, arm) for f, s in scen] for arm in ("A", "S", "B", "C")}
        keys = list(rows["A"][0])
        means = {arm: {k: float(np.mean([r[k] for r in rows[arm]])) for k in keys} for arm in rows}
        paired = {}
        br = np.random.default_rng(7)
        for arm in ("S", "B", "C"):
            paired[arm] = {}
            for k in keys:
                dlt = np.array([rows[arm][i][k] - rows["A"][i][k] for i in range(len(scen))])
                bs = dlt[br.integers(0, len(dlt), (4000, len(dlt)))].mean(1); lo, hi = np.percentile(bs, [2.5, 97.5])
                paired[arm][k] = {"delta": float(dlt.mean()), "ci95": [float(lo), float(hi)],
                                  "significant": bool(lo > 0 or hi < 0)}
        out["vessels"][vn] = {"means": means, "paired_vs_A": paired, "families": [f for f, _ in scen]}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    for vn, v in out["vessels"].items():
        m = v["means"]
        print(f"== {vn}")
        for k in m["A"]:
            ca = m["A"][k]
            f = lambda x: f"{100 * (x - ca) / ca:+.1f}%" if ca else "n/a"
            sig = lambda arm: "*" if v["paired_vs_A"][arm][k]["significant"] else " "
            print(f"  {k:16} A {ca:9.3f} | S70 {m['S'][k]:9.3f} {f(m['S'][k])}{sig('S')} | B {m['B'][k]:9.3f} {f(m['B'][k])}{sig('B')} | C {m['C'][k]:9.3f} {f(m['C'][k])}{sig('C')}")


if __name__ == "__main__":
    main()
