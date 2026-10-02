# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Problem map 13: runaway AI agents (loops, recursive spawning, overnight five-figure bills; Dark Reading).

Plant (1-minute steps, 24 hours; 40 agents)
  every agent does work: tool/model calls that cost money, sub-agent spawns, outbound calls; honest agents have
  their own rhythm and legitimate bursts (a big task can run at 3-6x its usual rate for 10-60 minutes)
  rogue onsets (random agent, random time):
    loop        spend rate jumps 10-40x (retry / self-call loop)
    fork        spawns sub-agents that each spend and spawn (doubling)
    exfil       calls to non-allow-listed destinations
    escalate    attempts at forbidden APIs (secrets, cluster-admin)
  enforcement layers common to every arm: RBAC denies forbidden APIs and a NetworkPolicy blocks non-allow-listed
  egress (both blocked at the source); attempts are still observable
Arms
  native_static    per-agent daily budget cap ($150) and a quota of 20 sub-agents: stops an agent when a cap is hit
  native_tight     the same with caps sized to stop runaways early ($40, 5 sub-agents): the operator's other choice
  omni             one engine per agent; observes spend rate against the agent's own baseline (queue), spawn rate
                   (load), denied attempts (security_block), rate change (drift); actions: throttle (halve the
                   agent's rate) when the engine's integrated need I_U or E rises; contain (freeze + revoke + audit)
                   when a denied attempt is seen or pressure persists past the dwell; release throttle when calm
  omni_no_engine   same mapping, engine not evolved
Gauges: rogue overspend ($ spent by rogue agents after onset), time to contain (minutes), peak sub-agents, honest
agents stopped (false stops), honest work completed (%), forbidden actions executed (always 0: RBAC), audit lines.
"""
from __future__ import annotations

import numpy as np

from omnilab.common import engine_for

STEPS = 1440
AGENTS = 40
GAUGES = {"rogue_overspend_usd": "lower", "time_to_contain_min": "lower", "peak_subagents": "lower",
          "false_stops": "lower", "honest_work_pct": "higher", "forbidden_executed": "lower"}
ARMS = ["native_static", "native_tight", "omni", "omni_no_engine"]
THROTTLE_I, CONTAIN_DWELL, RATIO_HI = 0.8, 8, 8.0   # chosen on development seeds 1-8


def scenario(seed):
    rng = np.random.default_rng(seed)
    base = rng.uniform(0.01, 0.08, AGENTS)            # $/min
    rate = np.tile(base, (STEPS, 1)) * (1 + 0.3 * rng.standard_normal((STEPS, AGENTS))).clip(0.2)
    for a in range(AGENTS):
        for _ in range(int(rng.integers(0, 4))):
            c = int(rng.integers(0, STEPS)); w = int(rng.integers(10, 60))
            rate[c:c + w, a] *= rng.uniform(3, 6)
    rogues = []
    for _ in range(int(rng.integers(2, 6))):
        a = int(rng.integers(0, AGENTS)); t0 = int(rng.integers(60, STEPS - 120))
        kind = str(rng.choice(["loop", "fork", "exfil", "escalate"]))
        rogues.append((a, t0, kind, float(rng.uniform(10, 40))))
    return {"rate": rate, "base": base, "rogues": rogues, "seed": seed}


def run(sc, arm):
    rate, base = sc["rate"], sc["base"]
    rog = {a: (t0, kind, m) for a, t0, kind, m in sc["rogues"]}
    spent = np.zeros(AGENTS); subs = np.zeros(AGENTS)
    stopped = np.zeros(AGENTS, bool); throttled = np.zeros(AGENTS, bool)
    stop_t = {}; over = 0.0; peak = 0.0; honest_done = honest_want = 0.0
    press = np.zeros(AGENTS, int)
    engs = [engine_for(arm) for _ in range(AGENTS)] if arm.startswith("omni") else None
    hist = [[] for _ in range(AGENTS)]
    cap_usd, cap_sub = (150.0, 20) if arm == "native_static" else (40.0, 5)
    for t in range(STEPS):
        for a in range(AGENTS):
            r = rate[t, a]; denied = 0.0; spawn = 0.0
            is_rogue = a in rog and t >= rog[a][0]
            if is_rogue:
                _, kind, m = rog[a]
                if kind == "loop":
                    r *= m
                elif kind == "fork":
                    spawn = max(1.0, subs[a]) * 0.3
                elif kind in ("exfil", "escalate"):
                    denied = 1.0; r *= 2.0
            want = r + subs[a] * base[a]
            if not is_rogue:
                honest_want += want
            if stopped[a]:
                continue
            got = want * (0.5 if throttled[a] else 1.0)
            spent[a] += got
            subs[a] += spawn * (0.5 if throttled[a] else 1.0)
            if is_rogue:
                over += got
            else:
                honest_done += got
            if not (throttled[a] or press[a]):
                hist[a].append(want)
            if arm.startswith("native"):
                if spent[a] >= cap_usd or subs[a] >= cap_sub:
                    stopped[a] = True; stop_t[a] = t
            else:
                bl = float(np.median(hist[a][-240:-10])) if len(hist[a]) > 30 else base[a]
                ratio = want / max(bl, 1e-6)
                d = engs[a].step(nodes=1, queue_ratio=min(2.0, max(0.0, ratio - 1.0) / 4.0),
                                 load_ratio=min(2.0, subs[a] / 5.0), security_block=denied,
                                 drift_ratio=min(1.5, max(0.0, ratio - 1.0) / 10.0))
                x = engs[a].x
                severe = ratio > RATIO_HI or subs[a] > 3
                throttled[a] = severe or float(x.I_U) > THROTTLE_I
                press[a] = press[a] + 1 if severe else 0
                if denied > 0 or press[a] >= CONTAIN_DWELL:
                    stopped[a] = True; stop_t[a] = t
        peak = max(peak, float(subs.sum()))
    ttc = [max(0, stop_t.get(a, STEPS) - t0) for a, (t0, _, _) in rog.items()]
    false = sum(1 for a in range(AGENTS) if stopped[a] and a not in rog) + \
        sum(1 for a, (t0, _, _) in rog.items() if a in stop_t and stop_t[a] < t0)
    return {"rogue_overspend_usd": over, "time_to_contain_min": float(np.mean(ttc)) if ttc else 0.0,
            "peak_subagents": peak, "false_stops": false, "honest_work_pct": honest_done / max(honest_want, 1e-9) * 100,
            "forbidden_executed": 0}
