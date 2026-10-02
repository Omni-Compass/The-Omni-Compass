# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Realm harness: every muscle native, watched and governed; every realm, and the whole tower, as one organism.

Arms, all on the same seed (the same demand, weather, disturbances):
  native  the plant and its native controller alone
  watch   the frozen governor reads the plant every period and writes nothing; must equal native exactly
  omni    the frozen governor holds the muscle's one knob; at 90% of the run it is killed, the knob returns to the
          native controller, and the harness checks that it did

The governor is omnicompass.adapter.Governor, unchanged (the engine with u = 0, the stack law, the kill switch).

Single muscle: one plant, one governor reading that plant.
Organism: all the plants of a realm (or all 656) on one 15 s clock, coupled: the electrical power of compute, motion
and process plants is heat in the realm's thermal zones; the organism's load swing is load on its storage sites; the
zones' temperature is the ambient every other plant reports. One governor reads the organism's aggregate and its one
directive sets every muscle's knob.

Primary outcome per seed: work per energy, omni against native: (work_omni / work_native) / (energy_omni /
energy_native) - 1. For an organism, work is the mean over its plants of work_omni / work_native (their work units
differ) and energy is total joules. Guardrails: work not lower by more than 1%; the share of periods in violation not
higher by more than 1 percentage point. Labels by rule (label()).
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List

from omnicompass.adapter import Governor, OBSERVE
from omnicompass.nervous_system import from_governor
from .plants import TEMPLATES, ThermalZone, EnergyStorage
from .bowl_arm import bowl_apply
from .presets import STEPS_SINGLE, ORGANISM_STEPS, CAL_SEED, params_for

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("native", "watch", "omni")
# for a setpoint muscle, a fourth arm: the native controller with the setpoint simply fixed at the band's calm end.
# It shows how much of any Omni result on that muscle the band alone would give, with no governor.
FIXED = "fixed_calm"
KILL_AT = 0.9
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
       11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 19: 2.093, 29: 2.045}


def catalog(path=None) -> List[dict]:
    return list(csv.DictReader((Path(path) if path else ROOT / "realms" / "catalog.csv").open()))


def seed_for(muscle_id: str, seed: int) -> int:
    h = 0
    for ch in f"{muscle_id}:{seed}":
        h = (h * 1000003 + ord(ch)) % 2_147_483_647
    return h


def make_plant(row, seed, organism=False):
    steps = ORGANISM_STEPS if organism else STEPS_SINGLE[row["template"]]
    p = TEMPLATES[row["template"]](params_for(row, organism), seed_for(row["muscle_id"], seed), steps)
    if row["template"] == "compute_pool" and not organism:
        p.budget_w = 1.25 * native_mean_power(row)
    return p


_CAL = {}


def native_mean_power(row):
    """A compute pool's declared power budget basis: its mean native draw on the calibration seed."""
    key = row["muscle_id"]
    if key not in _CAL:
        c = TEMPLATES[row["template"]](params_for(row), seed_for(key, CAL_SEED), STEPS_SINGLE[row["template"]])
        tot = 0.0
        for _ in range(c.steps):
            c.step()
            tot += c.power_w
        _CAL[key] = tot / c.steps
    return _CAL[key]


def calibrate_organism(rows):
    """Each plant's mean native power in the organism on the calibration seed: the organism's declared budget and
    coupling basis (the same for every arm and every result seed)."""
    key = tuple(r["muscle_id"] for r in rows)
    if key not in _CAL:
        nat = run_organism_arm(rows, CAL_SEED, "native", nominal=None)
        _CAL[key] = nat["mean_power"]
    return _CAL[key]


def authority(g, obs, d, clean):
    """The nervous system's authority after the governor's step, as the live controller computes it."""
    return from_governor(g, dict(obs, slo_clean=clean), d, mode="autopilot")


def _apply(plant, knob, g, d, auth):
    """Set the plant's override from the directive and authority; return it ({} when the knob is native)."""
    if g is None or not g.has_authority:
        plant.override = {}
        return {}
    plant.override = plant.omni_override(knob, d, g, auth)
    return plant.override


def _restored(plant, knob):
    return plant.override == {}


PACE_HIGH, PACE_LOW, PACE_HEAT = 0.95, 0.8, 0.96             # the live batch_pace defaults (omni_controller/muscles.py)


def pace(paced_plants, obs, auth):
    """The live batch_pace rule over the admission muscles: while hot, suspend the next running one; while calm, resume
    the first suspended one; one per decision either way. Band first: a job whose service is out of its line, or would
    leave it if held one more period, is never suspended, and if suspended it is resumed at once (fail up)."""
    if not paced_plants:
        return
    for p in paced_plants:
        if p.paced and not (p.slo_clean and p.can_hold()):
            p.paced = False
    hot = (obs["power_stress"] >= PACE_HIGH or obs["thermal"] >= PACE_HEAT
           or bool(auth and auth["organs"]["batch"].get("pause")))
    calm = obs["power_stress"] <= PACE_LOW and obs["thermal"] < PACE_HEAT - 0.06
    if hot:
        for p in paced_plants:
            if not p.paced and p.slo_clean and p.can_hold():
                p.paced = True
                return
    elif calm:
        for p in paced_plants:
            if p.paced:
                p.paced = False
                return


def run_muscle_arm(row, seed, arm):
    plant = make_plant(row, seed)
    knob = row["knob"]
    if arm == FIXED:
        for k in range(plant.steps):
            plant.override = plant.fixed_calm()
            plant.step()
        plant.finalize()
        return dict(plant.m, writes=0, after_kill_writes=0, restore_ok=True)
    g = None if arm in ("native", FIXED, "bowl") else Governor()
    if arm == "watch":
        g.set_mode(OBSERVE)
    kill_at = int(KILL_AT * plant.steps)
    writes = after_kill_writes = 0
    last = None
    restore_ok = True
    for k in range(plant.steps):
        if arm == "bowl":
            v = bowl_apply(plant, knob) if k < kill_at else {}
            if k >= kill_at:
                plant.override = {}
                restore_ok = restore_ok and _restored(plant, knob)
            elif v and v != last:
                writes += 1
            last = v
        elif g is not None:
            obs = plant.observe()
            if arm == "omni" and k == kill_at:
                g.kill()
            g.current_cap = 1.0                                    # as the live controller sets it
            d = g.step(obs, 0)
            auth = authority(g, obs, d, plant.slo_clean) if g.has_authority else None
            if knob == "admission" and g.has_authority and (row["template"] != "compute_pool" or plant.P.get("pausable")):
                pace([plant], obs, auth)
            v = _apply(plant, knob, g, d, auth)
            if v:
                if v != last:
                    writes += 1
                last = v
            if arm == "omni" and k >= kill_at:
                after_kill_writes += int(bool(v))
                restore_ok = restore_ok and _restored(plant, knob)
        plant.step()
    plant.finalize()
    m = dict(plant.m)
    m.update(writes=writes, after_kill_writes=after_kill_writes, restore_ok=restore_ok and after_kill_writes == 0)
    return m


def run_muscle(row, seed) -> Dict:
    out = {arm: run_muscle_arm(row, seed, arm) for arm in ARMS}
    if row["knob"] == "setpoint":
        out[FIXED] = run_muscle_arm(row, seed, FIXED)
    core = ("work", "energy_j", "viol", "steps")
    out["watch_equal"] = all(out["watch"][f] == out["native"][f] for f in core) and out["watch"]["writes"] == 0
    return out


# ---------------------------------------------------------------------------------------------------------------
class Body:
    """One organism's plants and its internal coupling: the electrical power of compute, motion and process plants is
    heat in its thermal zones, its load swing is load on its storage sites, and its zones' temperature is the ambient
    every other plant reports."""

    def __init__(self, rows, seed, nominal="calibrated"):
        self.rows = rows
        self.plants = [make_plant(r, seed, organism=True) for r in rows]
        if nominal == "calibrated":
            for p, w in zip(self.plants, calibrate_organism(rows)):
                p.nominal_w = max(w, 1.0)
        self.knobs = [r["knob"] for r in rows]
        self.paced = [p for p, r in zip(self.plants, rows) if r["knob"] == "admission"
                      and (r["template"] != "compute_pool" or p.P.get("pausable"))]
        self.zones = [p for p in self.plants if isinstance(p, ThermalZone)]
        self.stores = [p for p in self.plants if isinstance(p, EnergyStorage)]
        self.sources = [p for p in self.plants if not isinstance(p, (ThermalZone, EnergyStorage))]
        self.nom_src = sum(p.nominal_w for p in self.sources) or 1.0
        self.nom_sz = self.nom_src + sum(z.nominal_w for z in self.zones)
        self.nom_all = self.nom_sz + sum(s.nominal_w for s in self.stores)
        self.k_heat = [0.3 * z.P["q_it_w"] / (self.nom_src / len(self.zones)) for z in self.zones] if self.zones else []
        self.k_load = [0.3 * s.P["load_w"] / (self.nom_sz / len(self.stores)) for s in self.stores] if self.stores else []
        self.budget = 1.25 * self.nom_all
        self.src_w, self.sz_w, self.all_w = self.nom_src, self.nom_sz, self.nom_all
        self.psum = [0.0] * len(self.plants)

    def couple(self):
        zones = self.zones
        th = sum(z.zone_thermal() for z in zones) / len(zones) if zones else None
        for z, kh in zip(zones, self.k_heat):
            z.ext = {"heat_w": kh * self.src_w / len(zones)}
        for s, kl in zip(self.stores, self.k_load):
            s.ext = {"load_w": kl * (self.sz_w - self.nom_sz) / len(self.stores)}
        if th is not None:
            for p in self.plants:
                if not isinstance(p, ThermalZone):
                    p.ext["thermal"] = th

    def step(self):
        for i, p in enumerate(self.plants):
            p.step()
            self.psum[i] += p.power_w
        self.src_w = sum(p.power_w for p in self.sources)
        self.sz_w = self.src_w + sum(p.power_w for p in self.zones)
        self.all_w = self.sz_w + sum(p.power_w for p in self.stores)


def aggregate(bodies):
    """One governor's reading of the bodies it serves: the mean of every plant's observation, and power stress as the
    bodies' total draw against their total budget."""
    obs = [p.observe() for b in bodies for p in b.plants]
    n = len(obs)
    agg = {key: sum(o[key] for o in obs) / n for key in ("queue_ratio", "load_ratio", "network_stress", "drift_ratio",
                                                          "thermal")}
    agg.update(power_stress=sum(b.all_w for b in bodies) / sum(b.budget for b in bodies), stale=0.0,
               security_block=0.0)
    return agg


def run_bodies(bodies, arm, groups):
    """Run bodies on one 15 s clock. groups: lists of body indices, one governor per group (one group of all bodies is
    one governor over the whole stack; one group per body is a separate governor per body). arm native: no governor."""
    govs = []
    if arm not in ("native", "bowl"):
        for grp in groups:
            g = Governor()
            if arm == "watch":
                g.set_mode(OBSERVE)
            govs.append((g, [bodies[i] for i in grp]))
    kill_at = int(KILL_AT * ORGANISM_STEPS)
    writes = after_kill_writes = 0
    restore_ok = True
    last = {}
    for k in range(ORGANISM_STEPS):
        for b in bodies:
            b.couple()
        if arm == "bowl":
            for b in bodies:
                for p, knob in zip(b.plants, b.knobs):
                    if k >= kill_at:
                        p.override = {}
                        continue
                    v = bowl_apply(p, knob)
                    if v and v != last.get(id(p)):
                        writes += 1
                    last[id(p)] = v
        for g, bs in govs:
            agg = aggregate(bs)
            if arm == "omni" and k == kill_at:
                g.kill()
            g.current_cap = 1.0
            d = g.step(agg, 0)
            auth = {c: authority(g, agg, d, c) for c in (True, False)} if g.has_authority else {True: None, False: None}
            if g.has_authority:
                pace([p for b in bs for p in b.paced], agg, auth[True])
            for b in bs:
                for p, knob in zip(b.plants, b.knobs):
                    v = _apply(p, knob, g, d, auth[p.slo_clean])
                    if v:
                        if v != last.get(id(p)):
                            writes += 1
                        last[id(p)] = v
                    if arm == "omni" and k >= kill_at:
                        after_kill_writes += int(bool(v))
                        restore_ok = restore_ok and _restored(p, knob)
        for b in bodies:
            b.step()
    for b in bodies:
        for p in b.plants:
            p.finalize()
    return {"plants": [dict(p.m) for b in bodies for p in b.plants], "writes": writes,
            "after_kill_writes": after_kill_writes, "restore_ok": restore_ok and after_kill_writes == 0,
            "mean_power": [x / ORGANISM_STEPS for b in bodies for x in b.psum]}


def run_organism_arm(rows, seed, arm, nominal="calibrated"):
    return run_bodies([Body(rows, seed, nominal)], arm, [[0]])


def run_organism(rows, seed) -> Dict:
    out = {arm: run_organism_arm(rows, seed, arm) for arm in ARMS}
    out["watch_equal"] = out["watch"]["plants"] == out["native"]["plants"] and out["watch"]["writes"] == 0
    for arm in ARMS:
        out[arm].pop("mean_power", None)
    return out


# ---------------------------------------------------------------------------------------------------------------
def paired(arm_m, nat_m):
    """Per-seed contrasts of one muscle: primary, work change, violation-share change (percentage points)."""
    w = arm_m["work"] / nat_m["work"] if nat_m["work"] > 0 else (1.0 if arm_m["work"] == 0 else math.inf)
    e = arm_m["energy_j"] / nat_m["energy_j"] if nat_m["energy_j"] > 0 else math.nan
    v = (arm_m["viol"] / arm_m["steps"] - nat_m["viol"] / nat_m["steps"]) * 100.0
    return {"primary": w / e - 1.0, "work": w - 1.0, "energy": e - 1.0, "viol_pp": v}


def paired_organism(arm, nat):
    ws = [a["work"] / n["work"] for a, n in zip(arm["plants"], nat["plants"]) if n["work"] > 0]
    w = sum(ws) / len(ws)
    e = sum(a["energy_j"] for a in arm["plants"]) / sum(n["energy_j"] for n in nat["plants"])
    va = sum(a["viol"] for a in arm["plants"]) / sum(a["steps"] for a in arm["plants"])
    vn = sum(n["viol"] for n in nat["plants"]) / sum(n["steps"] for n in nat["plants"])
    return {"primary": w / e - 1.0, "work": w - 1.0, "energy": e - 1.0, "viol_pp": (va - vn) * 100.0}


def interval(xs):
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, m, m
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    t = T95.get(n - 1, 1.96)
    h = t * sd / math.sqrt(n)
    return m, m - h, m + h


def label(per_seed, valid=True):
    """Result label by rule (the GPU bench's rule, docs/GPU_PREREGISTRATION.md, amendment 1)."""
    if not valid or not all(all(math.isfinite(c[k]) for k in c) for c in per_seed):
        return "INVALID"
    p = interval([c["primary"] for c in per_seed])
    w = interval([c["work"] for c in per_seed])
    v = interval([c["viol_pp"] for c in per_seed])
    guard = w[1] >= -0.01 and v[2] <= 1.0
    if p[2] < 0:
        return "WORSE"
    if p[1] > 0:
        return "SUPERIOR WITHIN GUARDRAILS" if guard else "ENERGY IMPROVEMENT WITH SERVICE TRADEOFF"
    return "NONINFERIOR / INCONCLUSIVE" if guard else "NOT ESTABLISHED"


def summarize(per_seed):
    return {k: interval([c[k] for c in per_seed]) for k in ("primary", "work", "energy", "viol_pp")}


# ---------------------------------------------------------------------------------------------------------------
def run_stack(realm_rows, seed) -> Dict:
    """The four realm organisms stacked on one clock, every muscle as often as it appears (duplicates included), each
    realm keeping its own internal coupling. Arms:
      native     no governor
      separate   one governor per realm (as if each realm had its own Omni)
      one        one governor over the whole stack
    native_equal: the stacked native run reproduces each realm's own native run exactly, plant by plant."""
    out = {}
    for arm, groups in (("native", None), ("separate", [[i] for i in range(len(realm_rows))]),
                        ("one", [list(range(len(realm_rows)))])):
        bodies = [Body(rows, seed) for rows in realm_rows]
        out[arm] = run_bodies(bodies, "native" if arm == "native" else "omni", groups or [])
    alone = []
    for rows in realm_rows:
        alone += run_organism_arm(rows, seed, "native")["plants"]
    out["native_equal"] = alone == out["native"]["plants"]
    for arm in ("native", "separate", "one"):
        out[arm].pop("mean_power", None)
    return out
