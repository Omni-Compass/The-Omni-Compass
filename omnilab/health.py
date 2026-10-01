"""Problem map 8: GPU failures and stragglers (Llama 3: 419 interruptions in 54 days on 16K H100s; Lablup 2605.09370).

Plant (1-minute steps, 14 days)
  one synchronous training job on 2048 GPUs (256 nodes) + 8 spare nodes; step time = slowest node
  hard failures: per-GPU rate from Llama 3 (419 / 54 days / 16384 GPUs); the job stops and restarts from the last
  checkpoint (10-minute restart) on a spare
  stragglers: a node degrades (10-40% slower, HBM/thermal); 40% of degraded nodes hard-fail within a day
  checkpoint write costs 2 minutes of job time
Arms
  native_fixed      checkpoint every 60 min; stragglers never removed; failures handled by restart
  native_detect     checkpoint every 30 min; straggler detection by fixed threshold (node > 1.2x median for 10 min)
                    -> drain at once (restart from last checkpoint onto a spare)
  omni              checkpoint interval from Young/Daly, sqrt(2 C MTBF), with MTBF estimated online and shortened
                    while the engine's stress S is high; stragglers drained at the next checkpoint boundary (no lost
                    work) once the slowdown persists; engine observes failure rate (drift), slowdown (load) and the
                    count of degraded nodes (thermal)
  omni_no_engine    same mapping, engine not evolved
"""
from __future__ import annotations

import math

import numpy as np

from omnilab.common import engine_for

STEPS = 14 * 1440
NODES, SPARES, GPN = 256, 8, 8
RESTART, CKPT_COST = 10, 2
FAIL_PER_GPU_MIN = 419 / 54 / 16384 / 1440
GAUGES = {"goodput_pct": "higher", "lost_gpu_hours": "lower", "restarts": "lower", "straggler_node_hours": "lower",
          "checkpoint_overhead_pct": "lower"}
ARMS = ["native_fixed", "native_detect", "omni", "omni_no_engine"]
PERSIST, S_GAIN, CK_MULT = 5, 0.5, 0.5   # chosen on development seeds 1-8


def scenario(seed):
    rng = np.random.default_rng(seed)
    events = []
    p_fail = FAIL_PER_GPU_MIN * GPN * NODES
    p_deg = p_fail * rng.uniform(0.6, 1.2)
    for t in range(STEPS):
        if rng.random() < p_fail:
            events.append((t, "fail", int(rng.integers(0, NODES)), 0.0))
        if rng.random() < p_deg:
            node = int(rng.integers(0, NODES)); slow = float(rng.uniform(0.10, 0.40))
            events.append((t, "degrade", node, slow))
            if rng.random() < 0.4:
                events.append((t + int(rng.integers(30, 1440)), "fail", node, 0.0))
    events.sort()
    return {"events": events, "seed": seed}


def run(sc, arm):
    ev = sc["events"]; ei = 0
    slow = np.zeros(NODES)
    work = 0.0; since_ck = 0.0; ck_timer = 0; down = 0
    restarts = 0; strag_h = 0.0; ck_time = 0.0; lost = 0.0
    fail_times = []
    eng = engine_for(arm) if arm.startswith("omni") else None
    persist = np.zeros(NODES)
    interval = 60 if arm == "native_fixed" else 30
    drain_next = set()
    for t in range(STEPS):
        failed_now = []
        while ei < len(ev) and ev[ei][0] <= t:
            _, kind, node, s = ev[ei]; ei += 1
            if kind == "degrade":
                slow[node] = max(slow[node], s)
            else:
                failed_now.append(node)
        if failed_now:
            lost += since_ck; since_ck = 0.0; down = RESTART; restarts += 1
            for n in failed_now:
                slow[n] = 0.0; persist[n] = 0
            fail_times.append(t)
        if down > 0:
            down -= 1
            continue
        rate = 1.0 / (1.0 + slow.max())
        strag_h += float((slow > 0).sum()) / 60.0
        work += rate; since_ck += rate
        ck_timer += 1
        persist = np.where(slow > 0, persist + 1, 0)
        if arm == "native_detect":
            bad = np.where((slow > 0.2) & (persist >= 10))[0]
            if len(bad):
                lost += since_ck; since_ck = 0.0; down = RESTART; restarts += 1
                slow[bad] = 0.0; persist[bad] = 0
                continue
        if arm.startswith("omni"):
            if t % 5 == 0:
                recent = [x for x in fail_times if t - x < 1440]
                d = eng.step(nodes=NODES, load_ratio=float(slow.max()), drift_ratio=min(1.5, len(recent) / 4.0),
                             thermal=min(1.5, float((slow > 0).sum()) / 4.0))
            mtbf = (t + 1) / max(1, len(fail_times)) if fail_times else 1440.0
            mtbf *= 1.0 / (1.0 + S_GAIN * max(0.0, float(eng.x.S)) + max(0.0, float(eng.x.E)))
            interval = int(min(240, max(10, CK_MULT * math.sqrt(2.0 * CKPT_COST * mtbf))))
            for n in np.where(persist >= PERSIST)[0]:
                drain_next.add(int(n))
        if ck_timer >= interval:
            ck_timer = 0; since_ck = 0.0; ck_time += CKPT_COST; work -= CKPT_COST * rate
            if drain_next:
                for n in drain_next:
                    slow[n] = 0.0; persist[n] = 0
                drain_next = set()
    total = STEPS
    return {"goodput_pct": (work - lost) / total * 100, "lost_gpu_hours": lost * NODES * GPN / 60.0,
            "restarts": restarts, "straggler_node_hours": strag_h, "checkpoint_overhead_pct": ck_time / total * 100}
