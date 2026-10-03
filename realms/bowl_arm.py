# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The bowl law on every realm muscle (omnicompass/bowl.py): each plant's knob held by its own bowl.

Each plant's service is read as one position in its bowl (0 calm, 1 the line): the worst of its queue or lateness, its
load above half, and, for a storage site, its draw on the grid connection above half. The last period in violation
reads as past the wall (fail up). The bowl's force moves the knob: a positive force adds capacity, power, cooling or
protection, a negative force gives it back, each knob inside its own cover. At the kill every knob returns to native.

Knob by plant (the override key the plant already obeys, its native value, its cover, and which way is "more"):
  compute_pool   power: limit share 0.4-1; replicas-type: the HPA target held at native (loosening it past the
                 operator's own costs the service time, the same rule as the card's speed floor); machine pools: one
                 machine released while the force is clearly down and the machines left cover the recent peak with
                 margin (RELEASE_MARGIN); admission: native
  thermal_zone   setpoint between the band's stress (colder, more cooling) and calm ends; units: one released while the
                 force is clearly down; power: 0.5-1
  energy_storage reserve between the band's ends (a lower reserve gives the battery to the site); power: native
  motion_axis    speed and effort: 0.4-1
  process_loop   setpoint from native toward the band's calm end; actuator range 0.3-1; power 0.4-1
"""
from __future__ import annotations

from omnicompass.bowl import Band, Bowl, clamp

UP, DOWN, RELEASE = 0.10, 0.02, -0.2
RELEASE_MARGIN = 0.6     # a machine goes back only when the rest covers the recent peak at 0.6 of the plant's own release level


def position(plant) -> float:
    if plant.vhist and plant.vhist[-1]:
        return 1.0
    if plant.template == "thermal_zone":                       # a zone's service is its temperature against its limit
        P = plant.P
        return (plant.T - min(P["stress"], P["calm"])) / (P["t_limit"] - min(P["stress"], P["calm"]))
    o = plant.observe()
    p = max(o["queue_ratio"], (o["load_ratio"] - 0.5) / 0.5)
    if plant.template == "energy_storage":
        p = max(p, (o["power_stress"] - 0.5) / 0.5)
    return p


def release_safe(plant) -> bool:
    """A discrete unit goes back only when what is left covers the recent peak (the plant's own release window), with
    RELEASE_MARGIN of headroom on a machine pool: a machine boots in minutes, so a burst that arrives after a release
    is served late until it is back."""
    P = plant.P
    if plant.template == "compute_pool":
        from .plants import RELEASE_WINDOW, RELEASE_FRAC
        n = plant.n
        return (n > P["n_min"] and not plant.pending and plant.Q <= 0.0
                and len(plant.ahist) == RELEASE_WINDOW * P["startup_steps"]
                and max(plant.ahist) / ((n - 1) * plant.mu(plant.cap)) <= RELEASE_FRAC * 0.95 * RELEASE_MARGIN)
    u = plant.units_on
    return u > 1 and plant.T <= plant.setpoint() and plant.qc_cmd_avg / ((u - 1) * P["q_unit_w"]) <= 0.8


def lever(plant, knob):
    """(override key, native value, low, high, sign): sign +1 when a higher value is more capacity."""
    P, t = plant.P, plant.template
    if knob == "admission":
        return None
    if t == "compute_pool":
        if knob == "power":
            return ("power", 1.0, 0.4, 1.0, 1)
        if P.get("ca"):
            return ("release", None, 0, 0, 0)
        return None                                            # the HPA target is held at the operator's own
    if t == "thermal_zone":
        if knob == "setpoint":
            return ("setpoint", P["t_set"], min(P["stress"], P["calm"]), max(P["stress"], P["calm"]), -1)
        if knob == "capacity":
            return ("release", None, 0, 0, 0)
        return ("power", 1.0, 0.5, 1.0, 1)
    if t == "energy_storage":
        if knob == "setpoint":
            return ("setpoint", P["reserve"], min(P["stress"], P["calm"]), max(P["stress"], P["calm"]), -1)
        return None                                            # a battery's power limit gives nothing back: native
    if t == "motion_axis":
        return ("power", 1.0, 0.4, 1.0, 1) if knob == "power" else ("capacity", 1.0, 0.4, 1.0, 1)
    if t == "process_loop":
        if knob == "setpoint":
            lo, hi = min(P["sp"], P["calm"]), max(P["sp"], P["calm"])
            return ("setpoint", P["sp"], lo, hi, 1 if P["sp"] > P["calm"] else -1)
        if knob == "power":
            return ("power", 1.0, 0.4, 1.0, 1)
        return ("capacity", 1.0, 0.3, 1.0, 1)
    return None


def bowl_apply(plant, knob, dt=1.0, tau=3.0):
    """One decision: the plant's bowl reads its position and moves its knob. Returns the override written."""
    lv = lever(plant, knob)
    if lv is None:
        plant.override = {}
        return {}
    if not hasattr(plant, "_bowl"):
        plant._bowl = Bowl(Band(0.0, 1.0), dt=dt, tau=tau, kp=1.0, smooth=0.3)
        plant._bowl.kd *= 3.0
        plant._bowl_x = lv[1]
    b = plant._bowl
    F = b.force(position(plant))
    key, native, lo, hi, sign = lv
    if key == "release":
        ok = F < RELEASE and b.p < b.band.center and release_safe(plant)
        plant.override = {"release": 1.0} if ok else {}
        return plant.override
    span = hi - lo
    if b.p >= b.band.wall_high:
        x = hi if sign > 0 else lo                                 # fail up: full capacity at once
    else:
        g = UP if F > 0 else DOWN
        x = clamp(plant._bowl_x + sign * g * F * span, lo, hi)
    plant._bowl_x = x
    plant.override = {} if abs(x - native) < 1e-9 else {key: x}
    return plant.override
