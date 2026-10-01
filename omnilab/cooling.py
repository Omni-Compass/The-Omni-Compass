"""Problem map 10: cooling. Industry PUE has sat near 1.54 for six years (Uptime 2025).

Plant (5-minute steps, 7 days; one 10 MW data hall with chillers and a water-side economizer)
  IT load L(t) (diurnal + bursts, 4-10 MW); outdoor wet-bulb Twb(t) (diurnal + weather, seed-dependent climate)
  heat removed = IT power; chiller COP = 5.0 (1 + 0.035 (Tsw - 7)) (1 - 0.015 (Twb - 15)), Tsw = chilled-water supply
  economizer: full free cooling when Twb + 4 <= Tsw - 1, partial over the next 3 C; free cooling costs 5% of heat
  air side: fan speed f in [0.5, 1]; fan power 0.35 MW f^3 (per 10 MW); server inlet
      Tin = Tsw + 3 + 6 (L / 10 MW) / f + measurement noise, and the controller sees Tin one step late
  facility overhead (lighting, UPS losses) 4% of IT
  ASHRAE recommended inlet upper limit 27 C; minutes above it are violations
Arms
  native_fixed    Tsw 10 C, fans 100% (conservative, common)
  native_reset    outdoor-air reset of Tsw (8-16 C) and a fan controller holding Tin <= 24 C
  omni            each step chooses (Tsw, f) with the lowest cooling power whose predicted Tin stays under
                  27 C - margin, margin = 1.0 + 3 thermal-state (the engine's E): the engine observes inlet
                  temperature (thermal) and IT load (power_stress) and widens the margin while heat is building
  omni_no_engine  same mapping, engine not evolved
"""
from __future__ import annotations

import math

import numpy as np

from omnilab.common import engine_for, diurnal

STEPS = 7 * 288
GAUGES = {"pue": "lower", "cooling_mwh": "lower", "inlet_violation_min": "lower", "max_inlet_c": "lower"}
ARMS = ["native_fixed", "native_reset", "omni", "omni_no_engine"]
MARGIN0, MARGIN_E = 1.5, 3.0   # chosen on development seeds 1-8


def scenario(seed):
    rng = np.random.default_rng(seed)
    load = np.clip(diurnal(rng, STEPS, 288, rng.uniform(5, 8), rng.uniform(0.1, 0.3), int(rng.integers(3, 12)),
                           rng.uniform(0.1, 0.3), (3, 36), 0.03), 3.0, 10.0)
    base = rng.uniform(4, 24)
    t = np.arange(STEPS)
    weather = np.repeat(np.cumsum(rng.standard_normal(STEPS // 36 + 1)) * 0.8, 36)[:STEPS]
    twb = base + 4 * np.sin(2 * math.pi * (t / 288 - 0.3)) + weather
    return {"load": load, "twb": twb, "noise": rng.standard_normal(STEPS) * 0.3, "seed": seed}


def cooling_mw(L, twb, tsw, f):
    fan = 0.35 * f ** 3 * L / 10.0 * 10.0 / 10.0
    cop = 5.0 * (1 + 0.035 * (tsw - 7)) * (1 - 0.015 * (twb - 15))
    econ = min(1.0, max(0.0, ((tsw - 1) - (twb + 4)) / 3.0 + 1.0)) if twb + 4 <= tsw + 2 else 0.0
    chill = (1 - econ) * L / max(cop, 1.0) + econ * 0.05 * L
    return fan + chill


def inlet(L, tsw, f):
    return tsw + 3 + 6 * (L / 10.0) / f


def run(sc, arm):
    load, twb, noise = sc["load"], sc["twb"], sc["noise"]
    tsw, f = 10.0, 1.0
    eng = engine_for(arm) if arm.startswith("omni") else None
    cool = it = 0.0; viol = 0; tmax = 0.0
    seen_L = load[0]; seen_tin = inlet(load[0], tsw, f)
    for i in range(STEPS):
        L = load[i]
        if arm == "native_reset":
            tsw = float(np.clip(16 - 0.4 * max(0.0, twb[i] - 10), 8, 16))
            f = float(np.clip(f + 0.1 * (seen_tin - 24.0), 0.5, 1.0))
        elif arm.startswith("omni"):
            eng.step(thermal=min(1.5, seen_tin / 27.0), power_stress=min(1.5, seen_L / 10.0))
            margin = MARGIN0 + MARGIN_E * max(0.0, float(eng.x.E))
            best = None
            for ts in np.arange(8.0, 20.01, 0.5):
                for ff in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
                    if inlet(seen_L * 1.05, ts, ff) <= 27.0 - margin:
                        c = cooling_mw(seen_L, twb[i], ts, ff)
                        if best is None or c < best[0]:
                            best = (c, ts, ff)
            if best:
                _, tsw, f = best
            else:
                tsw, f = 8.0, 1.0
        tin = inlet(L, tsw, f) + noise[i]
        c = cooling_mw(L, twb[i], tsw, f)
        cool += c / 12.0; it += L / 12.0
        viol += 5 * (tin > 27.0); tmax = max(tmax, tin)
        seen_L, seen_tin = L, tin
    return {"pue": (it + cool + 0.04 * it) / it, "cooling_mwh": cool, "inlet_violation_min": viol, "max_inlet_c": tmax}
