# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""schedutil, kernel-shaped (kernel/sched/cpufreq_schedutil.c, frequency-invariant case), and the Omni-Compass ceiling.

  get_next_freq:  freq = (f_max + (f_max >> 2)) * util / max          # the >> 2 is the 1.25: tip at 80% utilisation
                  util: clamped by uclamp [uclamp_min, uclamp_max]; RT / deadline runnable -> util = max (policy max)
                  iowait boost: after an IO wakeup util is raised to the boost (doubling from a floor, decaying)
  rate limit:     a request inside rate_limit_us of the last change is dropped (the old frequency stays)
  resolve:        cpufreq_driver_resolve_freq -> the lowest OPP >= the request (CPUFREQ_RELATION_L), then clamped to
                  [scaling_min_freq, scaling_max_freq] (itself inside [cpuinfo_min_freq, cpuinfo_max_freq]); thermal and
                  PM QoS can lower the effective maximum
  Omni-Compass:   writes scaling_max_freq (the policy ceiling). It does not replace schedutil; schedutil keeps choosing
                  inside the ceiling. Kill switch: scaling_max_freq back to cpuinfo_max_freq.
Units: kHz for frequencies, microseconds for time, util in [0, max] with max = 1024 (SCHED_CAPACITY_SCALE).
Not modelled: intel_pstate / HWP (a different governor: the hardware picks within the limits), per-CPU PELT decay.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

SCALE = 1024


@dataclass
class Policy:
    opps: List[int]                       # available frequencies, kHz (cpuinfo range = [min(opps), max(opps)])
    scaling_min: Optional[int] = None
    scaling_max: Optional[int] = None     # the Omni-Compass ceiling
    thermal_max: Optional[int] = None     # thermal / PM QoS limit, if any
    rate_limit_us: int = 1000
    uclamp_min: int = 0
    uclamp_max: int = SCALE
    iowait_boost_min: int = 128
    cur: int = 0
    last_change_us: int = -10 ** 12
    iowait_boost: int = 0
    opps_sorted: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.opps_sorted = sorted(self.opps)
        self.cur = self.cur or self.opps_sorted[0]

    @property
    def cpuinfo_min(self):
        return self.opps_sorted[0]

    @property
    def cpuinfo_max(self):
        return self.opps_sorted[-1]

    def limits(self):
        lo = max(self.cpuinfo_min, self.scaling_min or self.cpuinfo_min)
        hi = min(self.cpuinfo_max, self.scaling_max or self.cpuinfo_max, self.thermal_max or self.cpuinfo_max)
        return lo, max(lo, hi)


def next_freq(p: Policy, util: int) -> int:
    """get_next_freq: (f_max + f_max/4) * util / max, frequency-invariant."""
    f = p.cpuinfo_max
    return (f + (f >> 2)) * util // SCALE


def resolve(p: Policy, target: int) -> int:
    """cpufreq_driver_resolve_freq: lowest OPP >= target within the policy limits (then clamp)."""
    lo, hi = p.limits()
    target = min(max(target, lo), hi)
    for f in p.opps_sorted:
        if f >= target and lo <= f <= hi:
            return f
    return max(f for f in p.opps_sorted if f <= hi) if any(f <= hi for f in p.opps_sorted) else lo


def update(p: Policy, now_us: int, util: int, rt: bool = False, iowait_wakeup: bool = False) -> int:
    """One schedutil update. Returns the frequency in effect after it."""
    if iowait_wakeup:
        p.iowait_boost = min(SCALE, max(p.iowait_boost_min, p.iowait_boost * 2))
    else:
        p.iowait_boost //= 2
    u = SCALE if rt else min(max(util, p.uclamp_min), p.uclamp_max)
    u = max(u, p.iowait_boost)
    if now_us - p.last_change_us < p.rate_limit_us:
        # the request is dropped, except that a lowered ceiling always applies at once
        lo, hi = p.limits()
        if p.cur > hi:
            p.cur = resolve(p, hi)
        return p.cur
    f = resolve(p, p.cpuinfo_max if rt else next_freq(p, u))
    if f != p.cur:
        p.cur = f; p.last_change_us = now_us
    return p.cur


def set_ceiling(p: Policy, khz: Optional[int]) -> None:
    """What Omni-Compass writes: scaling_max_freq. None restores cpuinfo_max_freq (the kill switch)."""
    p.scaling_max = p.cpuinfo_max if khz is None else max(p.cpuinfo_min, min(p.cpuinfo_max, int(khz)))
    lo, hi = p.limits()
    if p.cur > hi:
        p.cur = resolve(p, hi)
