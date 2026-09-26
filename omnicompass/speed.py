"""Speed-first allocation: the frozen six-state engine, a law that never trades response time for energy.

The frozen fleet law (adapter.AllocationLaw, FLEET_MODE) uses one number, rho*, both as the HPA target (how busy each
pod may run) and as the node-sizing target (how busy each machine may run). Saving machines therefore always meant
running pods hotter, which is where response time was lost. This law separates the two:

  pods      HPA target = rho* from the engine (equation: rho* = clamp(rho0 - kI I_U - kE E, rho_min, rho0)), with
            speed constants (rho0 near the latency knee) and the response-time nerve feeding the queue observation
  machines  sized to what the pods ask for, not to how busy they are:
            n_up   = ceil(requests / (cores * ALLOC) * (1 + headroom_up)) + ceil(kq * q * n)
            n_keep = ceil(peak requests over the last `window` decisions / (cores * ALLOC) * (1 + headroom))
            added at once when n < n_up (a pending pod costs response time);
            removed one per decision only when n >= n_keep + band for dwell decisions, no sooner than after_add
            decisions after an addition, and only while the engine's equation (2) push <= push_release
  power     cap = 1 whenever work is waiting or pods are busy above cap_busy; otherwise cap_idle
            (a cap slows service: S = S0 / cap, so capping a busy machine always costs response time)

The engine state (E, U, I_U, S, B, B_dot) is evolved by omnicompass.core unchanged; only this mapping is new.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from omnicompass.adapter import Governor, mode_law, AUTOPILOT


@dataclass(frozen=True)
class SpeedLaw:
    rho0: float = 0.60
    rho_min: float = 0.50
    kI: float = 0.10
    kE: float = 0.10
    kq: float = 0.50
    headroom: float = 0.10
    headroom_up: float = 0.0
    window: int = 10
    band: int = 1
    dwell: int = 5
    after_add: int = 5
    push_release: float = 0.05
    cap_idle: float = 1.0
    cap_busy: float = 0.30


class SpeedGovernor:
    def __init__(self, law: SpeedLaw = SpeedLaw()):
        self.law = law
        base = replace(mode_law("throughput"), rho0=law.rho0, rho_min=law.rho_min, kI=law.kI, kE=law.kE)
        self.g = Governor(law=base)
        self.g.set_mode(AUTOPILOT)
        self.streak = 0
        self.since_add = 99
        self.hist = []

    def step(self, obs, n, requests, cores_per_node):
        """Returns (hpa_target, node_target, power_cap)."""
        L = self.law
        self.g.nodes = n
        d = self.g.step(obs, 0)
        q = obs["queue_ratio"]
        self.hist = (self.hist + [requests])[-max(1, L.window):]
        n_up = math.ceil(requests / cores_per_node * (1.0 + L.headroom_up) - 1e-9) + math.ceil(L.kq * q * n)
        n_keep = math.ceil(max(self.hist) / cores_per_node * (1.0 + L.headroom) - 1e-9)
        tgt = n
        if n < n_up:
            tgt = n_up
            self.streak = 0
            self.since_add = 0
        else:
            self.since_add += 1
            if n >= max(n_keep, n_up) + L.band and q < 0.05:
                self.streak += 1
                if self.streak >= L.dwell and self.since_add >= L.after_add and self.g.last_push <= L.push_release:
                    tgt = n - 1
                    self.streak = 0
            else:
                self.streak = 0
        busy = obs["load_ratio"] > L.cap_busy or q > 0.0
        cap = 1.0 if busy or tgt > n else L.cap_idle
        return float(d["demand"]), int(tgt), cap
