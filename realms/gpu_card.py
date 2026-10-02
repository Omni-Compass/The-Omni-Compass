# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""A GPU card on its real physics, its own firmware, and the two-wire plug (evidence class S: a model, not a meter).

The card
  clock     f, a share of the top clock (1.0), moved by the firmware in bins of 0.9% (about 15 MHz on a 1.7 GHz part)
  power     P = idle + leakage(T) + P_dyn x busy x f x V(f)^2, with V(f) = 0.6 + 0.4 f: dynamic power rises with the
            clock and with the square of the voltage the clock needs, so the top of the clock range costs the most
  heat      C dT/dt = P - (T - T_amb) / R_th; leakage rises with temperature
  work      requests arrive (a slow wave, bursts, noise, drawn from the seed); the card serves f x mu per second;
            a request's response time is its wait plus its service time

The firmware (native, what ships on the card), 50 times a second
  boost     while there is work and room, raise the clock one bin, up to the clock ceiling
  hammer    while the draw is over the power limit, or the chip is over its slowdown temperature, drop three bins
  So the clock saws against the limit for as long as the work keeps coming: up a bin, knocked down three, up again.

The arms
  native    the card as shipped: power limit 150 W, clock ceiling at the top, firmware alone
  preset    a fixed efficiency preset: power limit 105 W (70%), as an operator would set and leave
  old       the shipped one-wire governor (omni_controller/gpu_governor.py, its defaults): the frozen engine's
            power_cap through the shield (draw x 1.3, 70% share floor, device minimum), the busy gate (smoothed
            utilization 0.5, band 0.1), the response-time reflex (p95 over 30 s against the line, clear after 3
            decisions), 5 W minimum change, every 2 s, the power limit only
  bowl      Omni-Compass through two wires (omnicompass/bowl.py): the clock ceiling is the up wire (how high boost may
            push), the power limit is the down wire (the lid, set just above what the ceiling draws, inside its cover
            of 105-150 W). The bowl's reading is the response time as a position between the bare service time (0)
            and the service line (1); the brain pulls it to the center. Both wires are restored to their snapshot at
            90% of the run, and the run checks they were.
"""
from __future__ import annotations

import math
import random
from typing import Dict

from omnicompass.adapter import Governor
from omnicompass.bowl import Band, Bowl, Plug, clamp
from omni_controller.gpu_governor import shield_limit, busy_gate

TICK = 0.02                 # firmware period, s
DECIDE = 1.0                # brain period, s
BIN = 0.009                 # one clock bin, share of the top clock
F_MIN = 0.12
P_IDLE, P_DYN = 22.0, 165.0
LEAK0, LEAK_T = 8.0, 0.02   # leakage at 40 C, and its rise per C
T_AMB, R_TH, C_TH = 30.0, 0.33, 90.0     # C, C/W, J/C  (150 W -> about 80 C, time constant about 30 s)
T_SLOW = 87.0
MU = 100.0                  # requests per second at the top clock
LIMIT_DEFAULT, LIMIT_MIN = 150.0, 105.0
SLO_S = 10.0 / MU           # the service line: ten bare service times (as the GPU bench sets it)


def volt(f):
    return 0.6 + 0.4 * f


def power(f, busy, T):
    return P_IDLE + LEAK0 * (1.0 + LEAK_T * (T - 40.0)) + P_DYN * busy * f * volt(f) ** 2


class Card:
    def __init__(self, seed: int, duration: float):
        r = random.Random(seed)
        n = int(duration / TICK)
        phase = r.uniform(0, 2 * math.pi)
        self.lam, left, amp, z = [], 0, 0.0, 0.0
        per = int(1.0 / TICK)
        for k in range(n):
            if k % per == 0:
                z = 0.85 * z + r.gauss(0, 0.05)
                if left <= 0 and r.random() < 0.02:
                    left, amp = r.randint(5, 25), r.uniform(0.1, 0.3)
                left -= 1
            wave = 0.45 + 0.15 * math.sin(2 * math.pi * k * TICK / 300.0 + phase)
            self.lam.append(max(0.0, MU * (wave + (amp if left > 0 else 0.0)) * math.exp(z)))
        self.n = n
        self.k = 0
        self.f, self.T, self.Q = 0.5, 45.0, 0.0
        self.last_p, self.last_busy = P_IDLE, 0.0
        self.limit, self.ceiling = LIMIT_DEFAULT, 1.0
        self.m = {"energy_j": 0.0, "served": 0.0, "arrived": 0.0, "hammer": 0, "reversals": 0, "viol_s": 0.0,
                  "t_peak": 0.0, "t_sum": 0.0, "f_sum": 0.0, "f_sq": 0.0}
        self.resp = []           # (response time, requests) per tick, for the percentiles
        self.last_dir = 0
        self.window = []         # response times this decision period
        self.bwin = []           # busy shares this decision period

    def tick(self):
        k = self.k
        a = self.lam[k] * TICK
        cap = self.f * MU * TICK
        served = min(self.Q + a, cap)
        self.Q += a - served
        busy = served / cap if cap > 0 else 1.0
        P = power(self.f, busy, self.T)
        self.T += (P - (self.T - T_AMB) / R_TH) * TICK / C_TH
        w = self.Q / (self.f * MU) + 1.0 / (self.f * MU)
        self.resp.append((w, a))
        self.window.append(w)
        self.bwin.append(busy)
        m = self.m
        self.last_p, self.last_busy = P, busy
        m["energy_j"] += P * TICK; m["served"] += served; m["arrived"] += a
        m["t_peak"] = max(m["t_peak"], self.T); m["t_sum"] += self.T
        m["f_sum"] += self.f; m["f_sq"] += self.f * self.f
        if w > SLO_S:
            m["viol_s"] += TICK
        # the firmware: boost up a bin, or the hammer down three
        if P > self.limit or self.T > T_SLOW:
            d = -3
            m["hammer"] += 1
        elif busy > 0.05 and self.f + BIN <= self.ceiling + 1e-9:
            d = 1
        elif self.f > self.ceiling + 1e-9:
            d = -1
        else:
            d = 0
        if d and self.last_dir and (d > 0) != (self.last_dir > 0):
            m["reversals"] += 1
        if d:
            self.last_dir = d
        self.f = clamp(self.f + d * BIN, F_MIN, 1.0)
        self.k += 1


class CeilingPlug(Plug):
    """The up wire: the clock ceiling the firmware may boost to (nvidia-smi -lgc on a real card; -rgc restores)."""
    def __init__(self, card):
        super().__init__(0.3, 1.0)
        self.card = card

    def _read_service(self):
        """The service as a position in its bowl: the worse of response time (bare service time 0, the line 1) and
        busy share (half busy 0, saturated 1). Response time is a cliff near saturation (a queue's wait grows as
        1 / (1 - busy)); busy share is the smooth coordinate under it, so the bowl sees the cliff coming."""
        w, b = self.card.window, self.card.bwin
        resp = (sum(w) / len(w) - 1.0 / MU) / (SLO_S - 1.0 / MU) if w else 0.0
        busy = (sum(b) / len(b) - 0.5) / 0.5 if b else 0.0
        return max(resp, busy)

    def _read_lever(self):
        return self.card.ceiling

    def _send(self, v):
        self.card.ceiling = round(v / BIN) * BIN if v < 1.0 else 1.0


class LimitPlug(Plug):
    """The down wire: the power limit, the lid (nvidia-smi -pl on a real card), whole watts."""
    def __init__(self, card):
        super().__init__(LIMIT_MIN, LIMIT_DEFAULT, tolerance=0.5)
        self.card = card

    def _read_service(self):
        return self.card.T

    def _read_lever(self):
        return self.card.limit

    def _send(self, v):
        self.card.limit = float(round(v))


def run(seed: int, arm: str, duration: float = 600.0, center: float = 0.5) -> Dict:
    card = Card(seed, duration)
    per = int(DECIDE / TICK)
    kill = int(0.9 * card.n)
    restored = True
    up = down = brain = None
    if arm == "preset":
        card.limit = LIMIT_MIN
    if arm == "bowl":
        up, down = CeilingPlug(card), LimitPlug(card)
        up.attach(); down.attach()
        brain = Bowl(Band(lo=0.0, hi=1.0, center=center), dt=DECIDE, tau=2.0, kp=1.0, authority=1.0, smooth=0.3)
        brain.kd *= 3.0                                  # the push: three times the damping that only stops the slosh,
                                                         # so a rising load is met before it reaches the wall
    if arm == "old":
        gov, lp_hist, util_avg, gated = Governor(), [], None, False
        old_per = int(2.0 / TICK)
    for k in range(card.n):
        if arm == "old" and k % old_per == 0 and k:
            if k >= kill:
                card.limit = LIMIT_DEFAULT                       # the kill: the limit read at start
            else:
                recent = card.resp[-int(30.0 / TICK):]
                tot = sum(a for _, a in recent) or 1.0
                acc, p95 = 0.0, recent[-1][0]
                for w, a in sorted(recent):
                    acc += a
                    if acc >= 0.95 * tot:
                        p95 = w; break
                lp = max(0.0, p95 / SLO_S - 1.0)
                lp_hist.append(lp)
                clean = len(lp_hist) >= 3 and all(x == 0.0 for x in lp_hist[-3:])
                gov.current_cap = min(1.0, card.limit / LIMIT_DEFAULT)
                d = gov.step({"queue_ratio": min(2.0, lp), "load_ratio": card.last_busy,
                              "power_stress": card.last_p / LIMIT_DEFAULT, "thermal": card.T / 83.0,
                              "network_stress": 0.0, "drift_ratio": 0.0, "stale": 0.0, "security_block": 0.0}, 0)
                cap = float(d["power_cap"]) if clean else 1.0
                want, _ = shield_limit(cap, card.last_p, LIMIT_DEFAULT, 100.0, 0.3, 0.70, clean)
                util_avg, gated = busy_gate(util_avg, card.last_busy, gated, 0.5, 0.1)
                if gated:
                    want = int(LIMIT_DEFAULT)
                want = max(want, int(LIMIT_MIN))
                if abs(want - card.limit) >= 5.0 or (want == LIMIT_DEFAULT and card.limit != want):
                    card.limit = float(want)
        if brain is not None and k % per == 0 and k:
            if k >= kill:
                if k - per < kill:
                    restored = up.restore() and down.restore()
            else:
                F = brain.force(up.read())
                if brain.p >= brain.band.wall_high:
                    c = up.write(1.0)                            # fail up: past the wall, the ceiling to the top at once
                else:
                    g = 0.10 if F > 0 else 0.02                  # up fast (service first), down gently
                    c = up.write(card.ceiling + g * F)
                lid = power(c, 1.0, card.T) * 1.06             # the lid just above what the ceiling draws, fully busy
                down.write(lid)
            card.window, card.bwin = [], []
        elif k % per == 0:
            card.window, card.bwin = [], []
        card.tick()
    m = dict(card.m)
    n = card.n
    rs = sorted(card.resp)
    tot = sum(a for _, a in rs) or 1.0

    def pct(q):
        acc = 0.0
        for w, a in rs:
            acc += a
            if acc >= q * tot:
                return w
        return rs[-1][0]
    mean_f = m["f_sum"] / n
    return {"energy_j": m["energy_j"], "served": m["served"], "work_per_kj": m["served"] / (m["energy_j"] / 1000.0),
            "p50_ms": 1000 * pct(0.5), "p95_ms": 1000 * pct(0.95), "p99_ms": 1000 * pct(0.99),
            "viol_share": m["viol_s"] / duration, "hammer_per_s": m["hammer"] / duration,
            "reversals_per_s": m["reversals"] / duration, "clock_mean": mean_f,
            "clock_jitter": math.sqrt(max(0.0, m["f_sq"] / n - mean_f ** 2)), "t_peak": m["t_peak"],
            "t_mean": m["t_sum"] / n, "backlog_end": card.Q, "restored": restored,
            "writes": (up.writes + down.writes) if up else 0}
