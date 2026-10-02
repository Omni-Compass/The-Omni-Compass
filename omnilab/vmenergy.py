# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Problem map 11: energy measurement inside VMs is impossible (no RAPL/IPMI in guests; kepler #2487).

This muscle is on the sensing side (afferent): how well each VM's energy is attributed, so savings can be proven.
Plant (10-second steps, 6 hours): a host with a real meter (RAPL/IPMI at the host) runs 8 VMs. True per-VM power
  = share of host idle (by vCPU count) + dynamic power that depends on CPU time AND on what the CPU is doing:
  memory-bound work draws less per busy second, vector (AVX) work more, and turbo raises power per unit of work
  when the host is lightly loaded. Only CPU time per VM is visible to the estimator (as in Kepler).
Arms
  native_kepler    Kepler-style model: fixed power per CPU-second trained on another machine, idle split by vCPUs
  native_ratio     host meter split by CPU-time share (uses the host meter, ignores workload type)
  omni             host meter + per-VM coefficients learned online (recursive least squares on the constraint that
                   VM powers sum to the host meter), with the engine's drift observation (meter residual) raising the
                   learning rate when the attribution goes stale
  omni_no_engine   same estimator, engine not evolved
Gauges: attribution error (mean absolute % per VM), worst VM error, total error vs the meter.
"""
from __future__ import annotations

import numpy as np

from omnilab.common import engine_for

STEPS = 6 * 360
VMS = 8
GAUGES = {"attr_error_pct": "lower", "worst_vm_error_pct": "lower", "total_error_pct": "lower"}
ARMS = ["native_kepler", "native_ratio", "omni", "omni_no_engine"]
LAM_BASE, LAM_FAST = 0.995, 0.97   # chosen on development seeds


def scenario(seed):
    rng = np.random.default_rng(seed)
    vcpu = rng.choice([2, 4, 8], VMS).astype(float)
    kind = rng.uniform(0.6, 1.5, VMS)                 # W per CPU-second relative factor (memory-bound .. AVX)
    cpu = np.zeros((STEPS, VMS))
    for v in range(VMS):
        base = rng.uniform(0.05, 0.8) * vcpu[v]
        cpu[:, v] = np.clip(base * (1 + 0.5 * np.sin(np.arange(STEPS) / rng.uniform(50, 400)))
                            * (1 + 0.2 * rng.standard_normal(STEPS)), 0, vcpu[v])
        c = int(rng.integers(0, STEPS - 400)); kind_shift = rng.uniform(0.7, 1.4)
        kind_t = np.full(STEPS, kind[v]); kind_t[c:] *= kind_shift  # the workload changes type part-way
        if v == 0:
            K = np.zeros((STEPS, VMS))
        K[:, v] = kind_t
    return {"cpu": cpu, "K": K, "vcpu": vcpu, "idle": float(rng.uniform(80, 150)), "w": float(rng.uniform(8, 14)),
            "noise": rng.standard_normal(STEPS) * 3.0, "seed": seed}


def truth(sc, t):
    cpu, K = sc["cpu"][t], sc["K"][t]
    load = cpu.sum() / sc["vcpu"].sum()
    turbo = 1.0 + 0.25 * (1.0 - load)
    dyn = sc["w"] * cpu * K[: len(cpu)] * turbo
    idle = sc["idle"] * sc["vcpu"] / sc["vcpu"].sum()
    return idle + dyn


def run(sc, arm):
    cpu, vcpu = sc["cpu"], sc["vcpu"]
    idle_share = sc["idle"] * vcpu / vcpu.sum()
    err = np.zeros(VMS); tot = np.zeros(VMS); tot_err = 0.0; tot_true = 0.0
    theta = np.full(VMS, 10.0); P = np.eye(VMS) * 100.0
    eng = engine_for(arm) if arm.startswith("omni") else None
    lam = LAM_BASE
    idle_est = None
    for t in range(STEPS):
        tr = truth(sc, t)
        meter = tr.sum() + sc["noise"][t]
        c = cpu[t]
        if arm == "native_kepler":
            est = idle_share + 10.0 * c
        elif arm == "native_ratio":
            share = c / max(c.sum(), 1e-9)
            est = idle_share + (meter - sc["idle"]) * share
        else:
            x = c
            y = meter - sc["idle"]
            pred = float(x @ theta)
            resid = y - pred
            k = P @ x / (lam + x @ P @ x)
            theta = theta + k * resid
            P = (P - np.outer(k, x @ P)) / lam
            theta = np.clip(theta, 1.0, 40.0)
            if t % 6 == 0:
                eng.step(drift_ratio=min(1.5, abs(resid) / max(y, 1.0) * 5.0))
                lam = LAM_FAST if float(eng.x.I_U) > 0.2 or float(eng.x.E) > 0.1 else LAM_BASE
            dyn = theta * x
            dyn = dyn * max(0.0, y) / max(dyn.sum(), 1e-9)   # honour the meter
            est = idle_share + dyn
        err += np.abs(est - tr); tot += tr
        tot_err += abs(est.sum() - tr.sum()); tot_true += tr.sum()
    per = err / np.maximum(tot, 1e-9) * 100
    return {"attr_error_pct": float(per.mean()), "worst_vm_error_pct": float(per.max()),
            "total_error_pct": tot_err / tot_true * 100}
