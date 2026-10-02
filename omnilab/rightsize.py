# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Problem map 1 and 2: idle capacity, and HPA + VPA that "cannot be used together on CPU/memory".

Plant (one service, 1-minute steps, 3 days)
  demand d(t) cores: diurnal with bursts and noise; memory per pod = m0 + m1 * (cores served per pod)
  pods n with CPU request r (cores) and memory request M (GiB); capacity = n * r (a pod can use its request)
  response time: M/M/c with c = n, u = d / (n r), service time 50 ms; unserved work queues (backlog)
  OOM kill when a pod's memory need exceeds M (pod restarts: lost for 1 minute, its work queues)
  cost = requested core-hours and requested GiB-hours (what the scheduler reserves, what nodes are bought for)
Arms
  native_hpa        HPA on CPU at 70% of request, static requests from the deployment (r0, M0) as most teams run
  native_hpa_vpa    HPA on CPU 70% + VPA (in-place mode, no restarts; the strongest VPA) every 5 minutes setting
                    r = 1.15 x p90 per-pod CPU and M = 1.15 x p90 per-pod memory over the last 8 hours:
                    the combination the Kubernetes project warns against (autoscaler #6247)
  native_turbonomic Turbonomic-style container resize every 10 minutes to p99 per-pod usage (aggressiveness p99),
                    HPA 70% left in place
  omni              one authority for replicas AND requests: the engine evolves on (queue, load, drift, memory
                    pressure); total CPU = d / rho* (rho* the engine's target), split into pods of the size the
                    service prefers; memory M = peak need over the last hour x (1 + margin), margin grown by the
                    engine's stress E; scale-in only while the engine's push reports convergence
  omni_no_engine    same mapping, engine not evolved
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from omnilab.common import engine_for, mmc_ms, wpct, diurnal

STEPS = 3 * 1440
S_MS = 50.0
GAUGES = {"cpu_core_hours": "lower", "mem_gib_hours": "lower", "p95_ms": "lower", "p99_ms": "lower",
          "oom_kills": "lower", "replica_reversals": "lower", "slo_breach_min": "lower", "work_done": "higher"}
RHO0, RHO_MIN, DOWN_DWELL, LOOKBACK, MEM_MARGIN, KI, KE = 0.80, 0.50, 5, 5, 1.25, 0.05, 0.40   # chosen on development seeds 1-8
ARMS = ["native_hpa", "native_hpa_vpa", "native_turbonomic", "omni", "omni_no_engine"]


def scenario(seed):
    rng = np.random.default_rng(seed)
    mean = rng.uniform(4, 20)
    d = diurnal(rng, STEPS, 1440, mean, rng.uniform(0.3, 0.7), int(rng.integers(2, 8)), rng.uniform(0.8, 2.5), (5, 90), 0.08)
    r0 = float(rng.choice([0.5, 1.0, 2.0]))
    return {"d": d, "r0": r0, "M0": float(rng.uniform(1.5, 3.0)) * r0, "m0": float(rng.uniform(0.2, 0.5)),
            "m1": float(rng.uniform(0.6, 1.2)), "mem_noise": float(rng.uniform(0.03, 0.12)), "seed": seed}


def run(sc, arm):
    rng = np.random.default_rng(sc["seed"] + 17)
    d = sc["d"]; r, M = sc["r0"], sc["M0"]
    n = max(2, math.ceil(d[0] / (r * 0.7)))
    eng = engine_for(arm, rho0=RHO0, rho_min=RHO_MIN, kI=KI, kE=KE) if arm.startswith("omni") else None
    backlog = 0.0; lat, wts = [], []
    cpu_h = mem_h = 0.0; ooms = 0; rev = 0; last_dir = 0; breach = 0; done = tot = 0.0
    hist_c, hist_m = deque(maxlen=480), deque(maxlen=480)
    peak_m = deque(maxlen=60); down_ok = 0; lost = 0
    for t in range(STEPS):
        live = max(1, n - lost); lost = 0
        cap = live * r
        want = d[t] + backlog
        srv = min(want, cap)
        u = min(0.99, d[t] / max(cap, 1e-9))
        wait_ms = backlog / max(cap, 1e-9) * 60000.0
        rt = mmc_ms(S_MS, u, live) + wait_ms
        backlog = want - srv; done += srv; tot += d[t]
        lat.append(rt); wts.append(d[t]); breach += rt > 500.0
        per_pod = srv / live
        mem_need = sc["m0"] + sc["m1"] * per_pod * (1.0 + sc["mem_noise"] * rng.standard_normal())
        if mem_need > M:
            k = max(1, int(round(live * min(1.0, (mem_need - M) / max(M, 1e-9) * 4))))
            ooms += k; lost = k
        hist_c.append(per_pod); hist_m.append(mem_need); peak_m.append(mem_need)
        cpu_h += n * r / 60.0; mem_h += n * M / 60.0
        metric = srv / max(n * r, 1e-9)
        new_n = n
        if arm.startswith("native"):
            ratio = metric / 0.7
            if abs(ratio - 1) > 0.1:
                new_n = max(2, math.ceil(n * ratio))
            if arm == "native_hpa_vpa" and t % 5 == 4 and len(hist_c) > 30:
                r = max(0.1, 1.15 * float(np.percentile(hist_c, 90)))
                M = max(0.25, 1.15 * float(np.percentile(hist_m, 90)))
            if arm == "native_turbonomic" and t % 10 == 9 and len(hist_c) > 30:
                r = float(min(r * 1.5, max(r * 0.5, float(np.percentile(hist_c, 99)))))
                M = float(min(M * 1.5, max(M * 0.5, float(np.percentile(hist_m, 99)))))
        else:
            q = min(2.0, backlog / max(cap, 1e-9))
            mem_p = max(0.0, max(peak_m) / max(M, 1e-9) - 0.8) * 2.0
            drift = abs(d[t] - d[t - 5]) / max(d[t], 1e-6) if t >= 5 else 0.0
            dd = eng.step(nodes=n, queue_ratio=q + (0.5 if rt > 500 else 0.0), load_ratio=min(2.0, metric),
                          drift_ratio=min(1.5, drift), thermal=min(1.5, mem_p))
            rho = float(dd["demand"])
            E = float(eng.x.E)
            total = (max(d[max(0, t - LOOKBACK + 1):t + 1]) + backlog / 5.0) / rho
            pods = max(2, math.ceil(total / sc["r0"]))
            if pods < n:
                down_ok = down_ok + 1 if eng.push <= 0.05 else 0
                new_n = n - 1 if down_ok >= DOWN_DWELL else n
                if down_ok >= DOWN_DWELL:
                    down_ok = 0
            else:
                down_ok = 0; new_n = pods
            r = max(0.1, total / new_n)
            M = max(0.25, max(peak_m) * (MEM_MARGIN + 0.5 * E))
        if new_n != n:
            dr = 1 if new_n > n else -1
            rev += int(last_dir != 0 and dr != last_dir); last_dir = dr
            n = new_n
    return {"cpu_core_hours": cpu_h, "mem_gib_hours": mem_h, "p95_ms": wpct(lat, wts, 95), "p99_ms": wpct(lat, wts, 99),
            "oom_kills": ooms, "replica_reversals": rev, "slo_breach_min": breach, "work_done": done / max(tot, 1e-9)}
