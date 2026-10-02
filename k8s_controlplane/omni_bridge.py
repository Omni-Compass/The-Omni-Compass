# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Wire Omni-Compass onto the 15s plant.

Default: Omni decides every omni_period_s (300s). HPA and CA keep their own
cadence. Modes:

  observe     compute and log; do not write
  target      write HPA target = ρ* only
  target_down write ρ* and own node scale-down (CA scale-up kept)
  full        ρ*, nodes, power cap, through the shield
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from omnicompass.adapter import (
    AUTOPILOT,
    OBSERVE,
    AllocationLaw,
    Governor,
    mode_law,
)
from omnicompass.nervous import tag_directive
from omnicompass.pools import apply_pool
from omnicompass.shield import ShieldLimits, enforce, violations

from .config import HarnessConfig


def make_governor(arm: str, law_over=None) -> Governor:
    if "throughput" in arm:
        law = mode_law("throughput")
    else:
        law = AllocationLaw()
    if "gate" in arm and not law_over:
        law_over = {"rho0": 0.95}
    if law_over:
        law = AllocationLaw(**{**law.__dict__, **law_over})
    gov = Governor(law=law, evolve="no_dynamics" not in arm)
    if "observe" in arm:
        gov.set_mode(OBSERVE)
    else:
        gov.set_mode(AUTOPILOT)
    return gov


def observe_from_plant(obs: Dict[str, Any], conflicts: int = 0) -> Dict[str, float]:
    return {
        "queue_ratio": float(obs["queue_ratio"]),
        "load_ratio": float(obs["load_ratio"]),
        "power_stress": float(obs["power_stress"]),
        "thermal": float(obs["thermal"]),
        "network_stress": 0.0,
        "drift_ratio": 0.0,
        "stale": 0.0,
        "security_block": float(obs["security"]),
        "conflicts": conflicts,
    }


class OmniLoop:
    def __init__(self, arm: str, cfg: HarnessConfig):
        self.arm = arm
        self.cfg = cfg
        self.gov = make_governor(arm, getattr(cfg, "omni_law", None))
        self.last_s = -10**9
        self.last_directive: Optional[Dict[str, Any]] = None
        self.fresh = False
        self.shield_hits = 0
        self.inv = 0
        self.inv_ex = 0

    @property
    def writes(self) -> bool:
        return self.gov.has_authority

    def maybe_step(self, now_s: int, plant_obs: Dict[str, Any], current_cap: float, nodes: int) -> Dict[str, Any]:
        if now_s - self.last_s < self.cfg.omni_period_s and self.last_directive is not None:
            self.fresh = False
            return self.last_directive
        self.fresh = True
        self.last_s = now_s
        self.gov.current_cap = current_cap
        self.gov.nodes = nodes
        raw = observe_from_plant(plant_obs)
        d = self.gov.step(raw, int(raw["conflicts"]))
        d = apply_pool(d, getattr(self.cfg, "pool", "elastic"))
        d = tag_directive(d, self.gov.has_authority, [])
        self.last_directive = d
        return d

    def apply_shield(self, actions, plant_obs, nodes, cap) -> list:
        st = {"actual_nodes": nodes, "power_cap": cap}
        cfg = type("C", (), {"minimum_nodes": self.cfg.ca.min_nodes, "maximum_nodes": self.cfg.ca.max_nodes})()
        lim = ShieldLimits(power_limit=1e9) if "throughput" in self.arm else ShieldLimits()
        vv = violations(actions, st, plant_obs, cfg, lim)
        self.inv += len(vv)
        self.inv_ex += sum(1 for v in vv if v != "I4")
        if "full" not in self.arm and "protect" not in self.arm and "throughput" not in self.arm:
            return actions
        out, hits = enforce(actions, st, plant_obs, cfg, lim)
        self.shield_hits += hits
        return out
