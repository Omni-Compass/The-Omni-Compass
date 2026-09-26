"""Problem map 7: AI training power swings (SemiAnalysis; Uptime; arXiv 2508.14318, 2606.04869).

Plant (0.1-second steps, 30 minutes)
  N synchronous GPUs: each iteration = compute (~700 W) then communication (~250 W); checkpoint stalls (150 W, 20 s)
  every 10 min; one job restart (60 s at idle, then back); site power = N x per-GPU power + facility base
  the grid operator publishes a ramp-rate limit that tightens when the grid is stressed:
      R_grid(t) = R0 (1 - 0.6 stress(t)),  stress(t) a slow random signal in [0, 1]
  a smoother can only (a) burn extra power in troughs (energy overhead) or (b) slow compute in ramps (throughput loss)
Arms
  native_none           no smoothing
  native_floor_safe     vendor-style power smoothing (GPU power floor + firmware ramp limits), set once for the worst
                        grid day: ramp limit 0.4 R0, floor 65% of compute power
  native_floor_nominal  the same set for the normal grid day: ramp limit R0, floor 40%
  omni                  the same two mechanisms (burn, slow), limit re-set every second from the grid signal through the
                        engine: power_stress = grid stress; applied limit = R_grid(t) x (margin - k E), E the engine's
                        energy state (tightens under sustained stress); the burn floor is only what the limit needs
  omni_no_engine        same mapping, engine not evolved
"""
from __future__ import annotations

import math

import numpy as np

from omnilab.common import engine_for

DT = 0.1
STEPS = int(30 * 60 / DT)
GAUGES = {"ramp_violation_s": "lower", "max_ramp_mw_s": "lower", "energy_overhead_pct": "lower",
          "throughput_loss_pct": "lower", "swing_1s_mw": "lower"}
ARMS = ["native_none", "native_floor_safe", "native_floor_nominal", "omni", "omni_no_engine"]
MARGIN, KE = 0.92, 0.3   # chosen on development seeds


def scenario(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(10000, 40000))
    pc, pm = rng.uniform(650, 750), rng.uniform(200, 300)
    tc, tm = rng.uniform(1.0, 3.0), rng.uniform(0.3, 1.0)
    p = np.zeros(STEPS); phase = np.zeros(STEPS, bool)
    t = 0.0; i = 0
    ck = int(600 / DT); restart = int(rng.integers(int(300 / DT), STEPS - int(120 / DT)))
    while i < STEPS:
        if i % ck == ck - 1:
            for k in range(int(20 / DT)):
                if i < STEPS: p[i] = 150; i += 1
            continue
        if restart <= i < restart + int(60 / DT):
            p[i] = 90; i += 1; continue
        for k in range(int(tc / DT)):
            if i < STEPS: p[i] = pc; phase[i] = True; i += 1
        for k in range(int(tm / DT)):
            if i < STEPS: p[i] = pm; i += 1
    site = n * p / 1e6 + 5.0
    s = np.cumsum(rng.standard_normal(STEPS // 10 + 1)) * 0.03
    s = (s - s.min()) / max(1e-9, s.max() - s.min())
    stress = np.repeat(s, 10)[:STEPS]
    r0 = rng.uniform(2.0, 6.0)                        # MW/s
    return {"site": site, "compute": phase, "stress": stress, "R0": r0, "n": n, "pc": pc, "seed": seed}


def run(sc, arm):
    site, stress, R0 = sc["site"], sc["stress"], sc["R0"]
    peak = site.max()
    eng = engine_for(arm) if arm.startswith("omni") else None
    out = np.zeros(STEPS); prev = site[0]
    burn = 0.0; lost = 0.0; comp = 0.0
    lim = R0
    hi_seen, lo_seen, run_lo, tm_est = site[0], site[0], 0, 0.0
    for i in range(STEPS):
        grid = R0 * (1.0 - 0.6 * stress[i])
        want = site[i]
        if arm == "native_none":
            p = want
        else:
            if arm == "native_floor_safe":
                lim, floor = 0.4 * R0, 0.65 * peak
            elif arm == "native_floor_nominal":
                lim, floor = R0, 0.40 * peak
            else:
                if i % 10 == 0:
                    eng.step(power_stress=float(stress[i]), load_ratio=float(want / peak))
                    lim = grid * max(0.5, MARGIN - KE * max(0.0, float(eng.x.E)))
                # learn the iteration rhythm: length of the last short trough (communication phase)
                mid = 0.5 * (hi_seen + lo_seen) if hi_seen > lo_seen else want
                if want < mid:
                    run_lo += 1
                else:
                    if 0 < run_lo * DT < 5.0:
                        tm_est = 0.7 * tm_est + 0.3 * run_lo * DT if tm_est else run_lo * DT
                    run_lo = 0
                hi_seen = max(0.999 * hi_seen, want); lo_seen = min(lo_seen * 1.001 + 1e-6, want)
                floor = hi_seen - lim * tm_est / 2.0 if (tm_est and run_lo * DT < 1.5 * tm_est) else 0.0
            lo, hi = prev - lim * DT, prev + lim * DT
            p = min(max(want, lo, floor), hi)
        if p > want:
            burn += (p - want) * DT
        if p < want and sc["compute"][i]:
            lost += (want - p) / max(want - 5.0, 1e-9) * DT
        if sc["compute"][i]:
            comp += DT
        out[i] = p; prev = p
    ramp = np.abs(np.diff(out)) / DT
    grid_lim = R0 * (1.0 - 0.6 * stress[1:])
    viol = float((ramp > grid_lim * 1.001).sum() * DT)
    sw = [out[k:k + 10].max() - out[k:k + 10].min() for k in range(0, STEPS - 10, 10)]
    return {"ramp_violation_s": viol, "max_ramp_mw_s": float(ramp.max()),
            "energy_overhead_pct": burn / max(float(site.sum() * DT), 1e-9) * 100,
            "throughput_loss_pct": lost / max(comp, 1e-9) * 100, "swing_1s_mw": float(np.mean(sw))}
