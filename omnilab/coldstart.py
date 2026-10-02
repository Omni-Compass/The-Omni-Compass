# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Problem map 5: cold starts / scale-from-zero latency (knative/serving #4902, #14202; KEDA http-add-on #219).

Plant (one scale-to-zero service, 1-second steps, 4 hours)
  arrivals A(t) req/s: idle gaps, recurring bursts (jittered, cron-like) and random sessions; service time 0.2 s;
  an instance serves K = 10 concurrent requests (50 req/s); cold start D seconds (seed: 2-10 s, image + runtime)
  requests beyond warm capacity queue; while no instance is warm they wait for the first one to boot
Arms
  native_knative   Knative KPA defaults: target concurrency K, stable window 60 s, panic window 6 s at 200%,
                   scale to zero after 60 s without traffic + 30 s grace
  native_keda      KEDA HTTP add-on defaults: polling every 30 s, cooldown 300 s before scale to zero
  omni             desired = ceil(concurrency / (K rho*)) on max(6 s, 60 s) averages, rho* from the engine; the engine
                   evolves on queue, load and the arrival trend (drift); keep-alive before scale to zero grows with
                   the engine's integrated need I_U (services that burst again are kept warm longer); one instance
                   pre-warmed when the rate trend is rising from idle
  omni_no_engine   same mapping, engine not evolved
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from omnilab.common import engine_for

STEPS = 4 * 3600
S = 0.2
K = 10
MU = K / S
GAUGES = {"cold_starts": "lower", "p95_ms": "lower", "p99_ms": "lower", "delayed_1s_pct": "lower",
          "instance_hours": "lower"}
ARMS = ["native_knative", "native_keda", "omni", "omni_no_engine"]
KEEP_BASE, KEEP_GAIN, RHO0, DOWN_S = 60, 600, 0.8, 30   # chosen on development seeds 1-8


def scenario(seed):
    rng = np.random.default_rng(seed)
    a = np.zeros(STEPS)
    period = int(rng.integers(300, 1800)); peak = rng.uniform(5, 80)
    t = int(rng.integers(0, period))
    while t < STEPS:
        w = int(rng.integers(20, 180)); a[t:t + w] += peak * rng.uniform(0.5, 1.5)
        t += period + int(rng.integers(-period // 5, period // 5 + 1))
    for _ in range(int(rng.integers(5, 25))):
        c = int(rng.integers(0, STEPS)); w = int(rng.integers(30, 900)); a[c:c + w] += rng.uniform(0.5, 10)
    arr = rng.poisson(a)
    return {"arr": arr.astype(float), "D": int(rng.integers(2, 11)), "seed": seed}


def run(sc, arm):
    arr, D = sc["arr"], sc["D"]
    inst = 0; booting = []
    q = 0.0
    hist = deque(maxlen=60)
    last_traffic = -10 ** 9
    colds = 0; inst_s = 0.0
    lat, wts = [], []
    eng = engine_for(arm, rho0=RHO0, rho_min=0.5) if arm.startswith("omni") else None
    rho = RHO0; keep = KEEP_BASE; prev_rate = 0.0; down = 0
    for t in range(STEPS):
        ready = sum(1 for b in booting if b <= t); inst += ready; booting = [b for b in booting if b > t]
        a = arr[t]
        if a > 0:
            last_traffic = t
        cap = inst * MU
        q += a
        srv = min(q, cap); q -= srv
        if a > 0:
            if inst == 0:
                nxt = min(booting) - t if booting else D
                wait = nxt + q / MU
            else:
                wait = q / max(cap, 1e-9)
            lat.append((S + wait) * 1000.0); wts.append(a)
        conc = (a + q) * S
        hist.append(conc)
        inst_s += inst + len(booting)
        c6 = float(np.mean(list(hist)[-6:])); c60 = float(np.mean(hist))
        total = inst + len(booting)
        want = total
        if arm == "native_knative":
            want = math.ceil(c60 / K)
            if total > 0 and c6 / K >= 2.0 * total:
                want = max(want, math.ceil(c6 / K))
            if want == 0 and t - last_traffic < 90:
                want = max(1, total) if total else 0
            if want == 0 and q > 0:
                want = 1
        elif arm == "native_keda":
            if t % 30 == 0 or (total == 0 and q > 0):
                want = max(1, math.ceil(c60 / K)) if (q > 0 or c60 > 0) else total
            if total > 0 and t - last_traffic >= 300 and c60 == 0:
                want = 0
        else:
            rate = float(np.mean(list(hist)[-10:])) / S
            trend = max(0.0, rate - prev_rate) / max(prev_rate, 1.0); prev_rate = 0.9 * prev_rate + 0.1 * rate
            if t % 5 == 0:
                d = eng.step(nodes=max(1, total), queue_ratio=min(2.0, q / max(cap, MU)),
                             load_ratio=min(2.0, conc / max(total * K, K)), drift_ratio=min(1.5, trend))
                rho = float(d["demand"])
                keep = KEEP_BASE + KEEP_GAIN * min(1.0, float(eng.x.I_U))
            want = math.ceil(max(c6 / (K * rho), c60 / K))
            if want == 0 and (t - last_traffic < keep or q > 0):
                want = max(1, total) if total else (1 if q > 0 else 0)
            if total == 0 and trend > 0.5 and rate > 0:
                want = max(want, 1)
            down = down + 1 if want < total else 0
            if want < total and down < DOWN_S:
                want = total
        if want > total:
            for _ in range(want - total):
                booting.append(t + D)
                if inst == 0:
                    colds += 1
        elif want < total:
            k = total - want
            c = min(k, len(booting)); booting = booting[c:]; inst -= min(inst, k - c)
    lat = np.array(lat); wts = np.array(wts)
    from omnilab.common import wpct
    return {"cold_starts": colds, "p95_ms": wpct(lat, wts, 95), "p99_ms": wpct(lat, wts, 99),
            "delayed_1s_pct": float(wts[lat > 1000].sum() / max(wts.sum(), 1) * 100), "instance_hours": inst_s / 3600.0}
