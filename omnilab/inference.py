# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Problem map 12: LLM inference autoscaling (KV cache fills before compute; vLLM, llm-d).

Plant (1-second steps, 2 hours; vLLM-like replicas, one GPU each)
  requests: Poisson with diurnal swing and bursts; prompt ~ lognormal (mean ~1000 tokens), output ~ lognormal (~250)
  replica: KV cache 200k tokens; prefill 10k tokens/s (chunked, shared); decode iteration 20 ms + 0.4 ms per running
  sequence (every running sequence gets one token per iteration); admission when the prompt fits in free KV;
  when KV overflows during decode the newest sequence is preempted (recomputed later: its progress is lost)
  routing: least KV-loaded replica; new replica ready after 90 s (model load); 1-32 replicas
  TTFT = queue wait + prefill; TPOT = decode iteration time; SLO: TTFT <= 2 s
Arms
  native_hpa_gpu   HPA on GPU utilisation (DCGM busy %) at 70%: the common default; busy % reads ~100% whenever
                   any sequence runs, so it over-scales
  native_keda      KEDA on vLLM num_requests_waiting, 5 waiting per replica, 15 s polling, 300 s cooldown
  omni             the engine's allocation law sizes replicas: load = KV-cache use, queue = waiting requests per
                   replica slot, drift = arrival trend; n_req = ceil(n load / rho*) + ceil(kq q n), scale-in only
                   while the engine's push reports convergence (the frozen Governor, throughput mode, decisions/15 s)
  omni_no_engine   same, engine not evolved
"""
from __future__ import annotations

import math

import numpy as np

from omnilab.common import engine_for, diurnal

STEPS = 7200
KV, PREFILL, BOOT, NMAX = 200_000, 10_000, 90, 32
GAUGES = {"ttft_p95_s": "lower", "ttft_p50_s": "lower", "tpot_p95_ms": "lower", "slo_breach_pct": "lower",
          "gpu_hours": "lower", "preemptions": "lower"}
ARMS = ["native_hpa_gpu", "native_keda", "omni", "omni_no_engine"]
LAW = dict(rho0=0.45, rho_min=0.35, kq=2.0, up_max=8, down_band=2, down_dwell=20, down_after_add=20)   # dev seeds


def scenario(seed):
    rng = np.random.default_rng(seed)
    lam = diurnal(rng, STEPS, STEPS, rng.uniform(2, 8), rng.uniform(0.3, 0.6), int(rng.integers(2, 6)),
                  rng.uniform(0.8, 2.0), (60, 600), 0.05)
    reqs = []
    for t in range(STEPS):
        for _ in range(rng.poisson(lam[t])):
            reqs.append((t, int(min(8000, rng.lognormal(math.log(800), 0.7))), int(min(2000, rng.lognormal(math.log(200), 0.8)))))
    return {"reqs": reqs, "seed": seed}


def run(sc, arm):
    reqs = sc["reqs"]; ri = 0
    reps = [{"seqs": [], "kv": 0.0} for _ in range(2)]
    booting = []
    queue = []                                 # [arrival, prompt, out]
    ttft, tpot = [], []
    gpu_s = 0.0; pre = 0; breach = 0; nreq = 0
    eng = engine_for(arm, **LAW) if arm.startswith("omni") else None
    keda_last_up = 0; cool = 0; prev_rate = 0.0; arr_hist = []
    for t in range(STEPS):
        for b in [b for b in booting if b <= t]:
            reps.append({"seqs": [], "kv": 0.0})
        booting = [b for b in booting if b > t]
        k = 0
        while ri < len(reqs) and reqs[ri][0] <= t:
            queue.append(list(reqs[ri])); ri += 1; k += 1
        arr_hist.append(k)
        # admission (FIFO), least KV-loaded replica
        still = []
        for q in queue:
            r = min(reps, key=lambda x: x["kv"])
            if r["kv"] + q[1] <= KV:
                r["seqs"].append({"arr": q[0], "p": q[1], "o": q[2], "done": 0.0, "pref": float(q[1]), "first": None})
                r["kv"] += q[1]
            else:
                still.append(q)
        queue = still
        busy_any = 0
        for r in reps:
            seqs = r["seqs"]
            if not seqs:
                continue
            busy_any += 1
            budget = PREFILL
            for s in seqs:
                if s["pref"] > 0 and budget > 0:
                    use = min(budget, s["pref"]); s["pref"] -= use; budget -= use
                    if s["pref"] <= 0:
                        s["first"] = t + 1
            dec = [s for s in seqs if s["pref"] <= 0]
            if dec:
                it = 0.020 + 0.0004 * len(dec)
                tok = 1.0 / it
                tpot.append(it * 1000.0)
                for s in dec:
                    g = min(tok, s["o"] - s["done"]); s["done"] += g; r["kv"] += g
                while r["kv"] > KV and len(seqs) > 1:
                    v = seqs.pop(); r["kv"] -= v["p"] + v["done"]; pre += 1
                    queue.insert(0, [v["arr"], v["p"], v["o"]])
            fin = [s for s in seqs if s["pref"] <= 0 and s["done"] >= s["o"]]
            for s in fin:
                seqs.remove(s); r["kv"] -= s["p"] + s["done"]
                w = (s["first"] or t) - s["arr"]; ttft.append(w); breach += w > 2.0; nreq += 1
        n = len(reps); total = n + len(booting)
        gpu_s += total
        want = total
        if arm == "native_hpa_gpu":
            if t % 15 == 0:
                util = busy_any / max(n, 1)
                ratio = util / 0.7
                if abs(ratio - 1) > 0.1:
                    want = max(1, min(NMAX, math.ceil(n * ratio)))
                if want < total:
                    cool = cool + 15 if cool < 300 else cool
                    want = total if cool < 300 else total - 1
                    if cool >= 300:
                        cool = 0
                else:
                    cool = 0
        elif arm == "native_keda":
            if t % 15 == 0:
                wantk = max(1, min(NMAX, math.ceil(len(queue) / 5.0))) if queue else 1
                if wantk > total:
                    want = wantk; keda_last_up = t
                elif wantk < total and t - keda_last_up >= 300:
                    want = total - 1; keda_last_up = t
        else:
            if t % 15 == 0:
                kv = sum(r["kv"] for r in reps) / (max(n, 1) * KV)
                rate = float(np.mean(arr_hist[-30:])); trend = max(0.0, rate - prev_rate) / max(prev_rate, 0.5)
                prev_rate = 0.8 * prev_rate + 0.2 * rate
                d = eng.step(nodes=total, queue_ratio=min(2.0, len(queue) / max(1.0, total * 8.0)),
                             load_ratio=min(2.0, kv), drift_ratio=min(1.5, trend))
                want = max(1, min(NMAX, total + int(d["node_delta"])))
        if want > total:
            booting += [t + BOOT] * (want - total)
        elif want < total:
            if booting:
                booting.pop()
            else:
                idle = [r for r in reps if not r["seqs"]]
                victim = idle[0] if idle else min(reps, key=lambda x: x["kv"])
                for s in victim["seqs"]:
                    queue.insert(0, [s["arr"], s["p"], s["o"]]); pre += 1
                reps.remove(victim)
    for q in queue:
        w = STEPS - q[0]; ttft.append(w); breach += w > 2.0; nreq += 1
    ttft = np.array(ttft) if ttft else np.zeros(1)
    return {"ttft_p95_s": float(np.percentile(ttft, 95)), "ttft_p50_s": float(np.percentile(ttft, 50)),
            "tpot_p95_ms": float(np.percentile(tpot, 95)) if tpot else 0.0, "slo_breach_pct": breach / max(nreq, 1) * 100,
            "gpu_hours": gpu_s / 3600.0, "preemptions": pre}
