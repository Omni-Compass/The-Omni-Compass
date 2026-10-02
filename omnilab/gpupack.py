# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Problem map 6: GPU utilisation ~5% and idle GPUs scattered across nodes (volcano #3948, kueue #5243).

Plant (1-minute steps, 2 days)
  16 nodes x 8 GPUs; a node can be powered off (5-minute boot); node base 1.0 kW, GPU 0.10 kW idle / 0.70 kW busy
  jobs arrive (diurnal Poisson) asking for 1, 2, 4 or 8 GPUs on ONE node, run 20 min - 12 h, checkpoint every 30 min
  fragmentation: a job waits although enough GPUs are free in total, because no single node has them
Arms
  native_spread    kube-scheduler default (LeastAllocated: node with most free GPUs); Cluster Autoscaler
                   (power a node on for pending jobs, off after 10 minutes empty)
  native_binpack   Volcano / KAI binpack (MostAllocated: fullest node that fits); same autoscaler
  omni             binpack placement; defragmentation: when a job is blocked only by fragmentation, the engine may
                   move small jobs at their next checkpoint (3-minute pause each) to free a whole node; nodes powered
                   off when empty only while the engine's push reports convergence, powered on ahead when the engine's
                   integrated need I_U rises; engine observes queue, load and fragmentation (drift)
  omni_no_engine   same mapping, engine not evolved
"""
from __future__ import annotations

import math

import numpy as np

from omnilab.common import engine_for

STEPS = 2 * 1440
NODES, G = 16, 8
BOOT = 5
GAUGES = {"wait_mean_min": "lower", "wait_p95_min": "lower", "energy_kwh": "lower", "idle_gpu_hours_powered": "lower",
          "frag_blocked_min": "lower", "jobs_done": "higher", "migrations": "lower"}
ARMS = ["native_spread", "native_binpack", "omni", "omni_no_engine"]
OFF_AFTER, PREWARM_I = 3, 0.3   # chosen on development seeds 1-8


def scenario(seed):
    rng = np.random.default_rng(seed)
    base = rng.uniform(0.05, 0.14)
    jobs = []
    for t in range(STEPS):
        lam = base * (1.0 + 0.6 * math.sin(2 * math.pi * t / 1440 + rng.uniform(0, 0.01)))
        for _ in range(rng.poisson(lam)):
            size = int(rng.choice([1, 2, 4, 8], p=[0.4, 0.25, 0.2, 0.15]))
            dur = int(np.clip(rng.lognormal(math.log(120), 1.0), 20, 720))
            jobs.append((t, size, dur))
    return {"jobs": jobs, "seed": seed}


def run(sc, arm):
    free = [G] * NODES
    on = [i < 4 for i in range(NODES)]; boot = [0] * NODES; empty_for = [0] * NODES
    running = []          # [node, size, remaining, next_ckpt, paused]
    pending = []          # [arrival, size, dur]
    arrivals = list(sc["jobs"]); ai = 0
    waits = []; energy = 0.0; idle_gpu_h = 0.0; frag = 0; done = 0; migr = 0
    eng = engine_for(arm) if arm.startswith("omni") else None
    binpack = arm != "native_spread"
    for t in range(STEPS):
        while ai < len(arrivals) and arrivals[ai][0] <= t:
            pending.append(list(arrivals[ai])); ai += 1
        for i in range(NODES):
            if boot[i] and boot[i] <= t:
                on[i] = True; boot[i] = 0
        # progress
        for j in running:
            if j[4] > 0:
                j[4] -= 1; continue
            j[2] -= 1; j[3] -= 1
            if j[3] <= 0:
                j[3] = 30
        for j in [j for j in running if j[2] <= 0]:
            free[j[0]] += j[1]; running.remove(j); done += 1
        # place (FIFO with backfill)
        still = []
        for p in pending:
            cands = [i for i in range(NODES) if on[i] and free[i] >= p[1]]
            if cands:
                i = min(cands, key=lambda k: (free[k], k)) if binpack else max(cands, key=lambda k: (free[k], -k))
                free[i] -= p[1]; running.append([i, p[1], p[2], 30, 0]); waits.append(t - p[0])
            else:
                still.append(p)
        pending = still
        tot_free = sum(free[i] for i in range(NODES) if on[i])
        blocked = [p for p in pending if tot_free >= p[1]]
        frag += bool(blocked)
        n_on = sum(on); used = sum(G - free[i] for i in range(NODES) if on[i])
        # controller
        need = sum(p[1] for p in pending)
        if arm.startswith("native"):
            if need > 0:
                want_nodes = math.ceil(max(0, need - tot_free) / G) if not blocked else math.ceil(need / G)
                for i in range(NODES):
                    if want_nodes <= 0:
                        break
                    if not on[i] and not boot[i]:
                        boot[i] = t + BOOT; want_nodes -= 1
            for i in range(NODES):
                if on[i] and free[i] == G:
                    empty_for[i] += 1
                    if empty_for[i] >= 10 and n_on > 1:
                        on[i] = False; empty_for[i] = 0; n_on -= 1
                else:
                    empty_for[i] = 0
        else:
            d = eng.step(nodes=max(1, n_on), queue_ratio=min(2.0, need / max(1, n_on * G)),
                         load_ratio=min(2.0, used / max(1, n_on * G)),
                         drift_ratio=min(1.5, (sum(p[1] for p in blocked) / max(1, tot_free)) if blocked else 0.0))
            if blocked:
                big = max(p[1] for p in blocked)
                donors = sorted([i for i in range(NODES) if on[i] and free[i] < G and free[i] > 0],
                                key=lambda k: G - free[k])
                if donors:
                    src = donors[0]
                    movers = [j for j in running if j[0] == src and j[4] == 0 and j[3] <= 1]
                    for j in movers:
                        dst = [k for k in range(NODES) if on[k] and k != src and free[k] >= j[1] and free[k] < G]
                        if dst:
                            k = min(dst, key=lambda x: free[x])
                            free[src] += j[1]; free[k] -= j[1]; j[0] = k; j[4] = 3; migr += 1
            unmet = max(0, need - tot_free) if not blocked else need
            if unmet > 0 or float(eng.x.I_U) > PREWARM_I and n_on * G - used < G:
                want_nodes = max(1, math.ceil(unmet / G))
                for i in range(NODES):
                    if want_nodes <= 0:
                        break
                    if not on[i] and not boot[i]:
                        boot[i] = t + BOOT; want_nodes -= 1
            for i in range(NODES):
                if on[i] and free[i] == G:
                    empty_for[i] += 1
                    if empty_for[i] >= OFF_AFTER and n_on > 1 and eng.push <= 0.05 and not pending:
                        on[i] = False; empty_for[i] = 0; n_on -= 1
                else:
                    empty_for[i] = 0
        busy = sum(G - free[i] for i in range(NODES) if on[i])
        for j in running:
            if j[4] > 0:
                busy -= 0  # paused jobs still hold GPUs (idle power)
        paused = sum(j[1] for j in running if j[4] > 0)
        powered = sum(on) + sum(1 for b in boot if b)
        energy += (powered * 1.0 + (busy - paused) * 0.70 + (powered * G - busy + paused) * 0.10) / 60.0
        idle_gpu_h += (powered * G - busy + paused) / 60.0
    for p in pending:
        waits.append(STEPS - p[0])
    w = np.array(waits, float) if waits else np.zeros(1)
    return {"wait_mean_min": float(w.mean()), "wait_p95_min": float(np.percentile(w, 95)), "energy_kwh": energy,
            "idle_gpu_hours_powered": idle_gpu_h, "frag_blocked_min": frag, "jobs_done": done, "migrations": migr}
