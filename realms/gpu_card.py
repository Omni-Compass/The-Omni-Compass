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

The work
  memb      the share of a request's time at the top clock spent waiting on memory, which does not speed up with the
            clock: 0 is compute-bound work (large matrix products, the bench's pinned workload), 0.85 is typical of AI
            token generation (each token streams the model's weights from memory). The card serves 1 / ((1 - memb) / f
            + memb) of its top speed

The arms: each base alone, and the same base with Omni-Compass on top (Omni never runs the card itself)
  native    the card as shipped: power limit 150 W, clock ceiling at the top, firmware alone
  omni      native + Omni-Compass on top, through two wires (omnicompass/bowl.py): the clock ceiling is the up wire (how
            high boost may push), the power limit is the down wire (the lid, set just above what the ceiling draws,
            never under the card's own busy draw). The bowl's reading is the response time as a position between the
            bare service time (0) and the service line (1); the brain pulls it to the center. The verdict
            (omnicompass/verdict.py) decides how far the ceiling may go: a step down is allowed only after a paired
            trial shows it costs each request at most ALLOW of the card's own time on it; where no step passes, the
            ceiling stays where the firmware has it. Both wires are restored to their snapshot at 90% of the run
  cap       a fixed power cap set by the operator and left (105 W, 70%), firmware alone under it
  cap_omni  the cap + Omni-Compass on top: the same law, the lid never above the operator's cap
"""
from __future__ import annotations

import math
import random
from typing import Dict

from omnicompass.bowl import Band, Bowl, Plug, clamp
from omnicompass.verdict import Verdict

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
# the law of omni_controller/gpu_bowl.py (docs/GPU_PREREGISTRATION.md, amendment 8): up and down gains (share of the top
# clock per unit of force), the bowl's center, the speed floor (a share of the card's own busy clock), the verdict's
# allowance (the most a step may add to the card's own time on a request) and how often it runs a trial (decisions)
UP, DOWN, CENTER, FLOOR, ALLOW, PROBE_EVERY = 0.10, 0.0125, 0.4, 1.0, 0.02, 8
OMNI = ("omni", "cap_omni")
SATURATED = 0.95            # busy share over a decision at which work is waiting: race, never pace


def volt(f):
    return 0.6 + 0.4 * f


def power(f, busy, T):
    return P_IDLE + LEAK0 * (1.0 + LEAK_T * (T - 40.0)) + P_DYN * busy * f * volt(f) ** 2


class Card:
    def __init__(self, seed: int, duration: float, memb: float = 0.0):
        r = random.Random(seed)
        self.memb = memb
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
        self.swin = []           # the card's own time per request this decision period (the wait in the queue left out)

    def tick(self):
        k = self.k
        a = self.lam[k] * TICK
        sp = 1.0 / ((1.0 - self.memb) / self.f + self.memb)
        cap = sp * MU * TICK
        served = min(self.Q + a, cap)
        self.Q += a - served
        busy = served / cap if cap > 0 else 1.0
        P = power(self.f, busy, self.T)
        self.T += (P - (self.T - T_AMB) / R_TH) * TICK / C_TH
        w = self.Q / (sp * MU) + 1.0 / (sp * MU)
        self.resp.append((w, a))
        self.window.append(w)
        self.bwin.append(busy)
        if a > 0:
            self.swin.extend([1.0 / (sp * MU)] * max(1, int(round(a))))
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
        """The service as a position in its bowl: response time only (bare service time 0, the line 1). A busy card is
        doing its work; being busy is not a breach and is not read as one."""
        w = self.card.window
        return (sum(w) / len(w) - 1.0 / MU) / (SLO_S - 1.0 / MU) if w else 0.0

    def _read_lever(self):
        return self.card.ceiling

    def _send(self, v):
        self.card.ceiling = round(v / BIN) * BIN if v < 1.0 else 1.0


class LimitPlug(Plug):
    """The down wire: the power limit, the lid (nvidia-smi -pl on a real card), whole watts."""
    def __init__(self, card, top=LIMIT_DEFAULT):
        super().__init__(LIMIT_MIN, top, tolerance=0.5)
        self.card = card

    def _read_service(self):
        return self.card.T

    def _read_lever(self):
        return self.card.limit

    def _send(self, v):
        self.card.limit = float(round(v))


def run(seed: int, arm: str, duration: float = 600.0, memb: float = 0.0) -> Dict:
    card = Card(seed, duration, memb)
    per = int(DECIDE / TICK)
    kill = int(0.9 * card.n)
    restored = True
    up = down = brain = vd = None
    base_limit = LIMIT_MIN if arm in ("cap", "cap_omni") else LIMIT_DEFAULT
    card.limit = base_limit
    events = {"trials": 0, "allowed": 0, "refused": 0}
    if arm in OMNI:
        up, down = CeilingPlug(card), LimitPlug(card, top=base_limit)
        up.attach(); down.attach()
        brain = Bowl(Band(lo=0.0, hi=1.0, center=CENTER), dt=DECIDE, tau=2.0, kp=1.0, authority=1.0, smooth=0.3)
        brain.kd *= 3.0                                  # the push: three times the damping that only stops the slosh,
                                                         # so a rising load is met before it reaches the wall
        vd = Verdict(tolerance=ALLOW, probe_every=PROBE_EVERY)
    learn_f, learn_p = [], []          # the card under its base while busy, ceiling at the top: its clock and its draw
    for k in range(card.n):
        if brain is not None and card.ceiling >= 1.0 and card.limit >= base_limit and card.last_busy >= 0.9:
            learn_f.append(card.f); learn_p.append(card.last_p)
        if brain is not None and k % per == 0 and k:
            if k >= kill:
                if k - per < kill:
                    restored = up.restore() and down.restore()
            else:
                F = brain.force(up.read())
                # the speed floor: never under the clock the card reaches under its base while busy (the top until 15
                # busy readings are in), so waiting work is never served slower than the base
                f_nat = sorted(learn_f[-10000:])[len(learn_f[-10000:]) // 2] if len(learn_f) >= 15 else 1.0
                p_nat = sorted(learn_p[-10000:])[int(0.9 * (len(learn_p[-10000:]) - 1))] if len(learn_p) >= 15 else base_limit
                b = card.bwin
                saturated = bool(b) and sum(b) / len(b) >= SATURATED
                # the verdict: what the last decision's requests cost the card at the step it stood at, then how far
                # the ceiling may go now (or the step a trial needs)
                vd.observe(card.swin)
                deepest, trial, ev = vd.tick(brain.p < brain.band.wall_high and not saturated)
                if ev:
                    key = {"trial": "trials", "step allowed": "allowed"}.get(ev["verdict"], "refused" if "refused" in ev["verdict"] else None)
                    if key:
                        events[key] += 1
                at_limit = card.last_p >= 0.97 * card.limit
                if saturated and at_limit and len(learn_f) >= 15:
                    # saturated against the card's own limit: hold at its own busy clock under that limit (amendment 9)
                    c = up.write(max(0.3, min(1.0, f_nat)))
                elif brain.p >= brain.band.wall_high or saturated:
                    # fail up past the wall; and race while work waits (the card saturated: a queue is forming), so a
                    # burst is always served at full speed; the bowl paces only the slack between bursts
                    c = up.write(1.0)
                elif trial:
                    c = up.write(1.0 - deepest * BIN)
                else:
                    g = UP if F > 0 else DOWN                    # up fast (service first), down gently
                    c_lo = max(min(1.0, f_nat * FLOOR), 1.0 - deepest * BIN)
                    c = up.write(max(c_lo, card.ceiling + g * F))
                # the lid just above what the ceiling draws fully busy, never under the card's own busy draw
                lid = max(power(c, 1.0, card.T), p_nat) * 1.06
                down.write(lid)
            card.window, card.bwin, card.swin = [], [], []
        elif k % per == 0:
            card.window, card.bwin, card.swin = [], [], []
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
            "writes": (up.writes + down.writes) if up else 0, "verdict_steps_allowed": vd.allowed if vd else 0,
            "verdict_events": events}
