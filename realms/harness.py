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
from .plants import TEMPLATES, ThermalZone, EnergyStorage
from .presets import STEPS_SINGLE, ORGANISM_STEPS, params_for

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
    return TEMPLATES[row["template"]](params_for(row, organism), seed_for(row["muscle_id"], seed), steps)


def _apply(plant, knob, g, d, last):
    """Set the plant's override from the directive; return the value written (None when nothing is held)."""
    if g is None or not g.has_authority:
        plant.override = {}
        return None
    v = plant.omni_value(knob, d, g)
    plant.override = {knob: v}
    return v


def _restored(plant, knob):
    nv = plant.native_value(knob)
    return plant.override == {} and (nv is None or plant.knob_value(knob) == nv)


def run_muscle_arm(row, seed, arm):
    plant = make_plant(row, seed)
    knob = row["knob"]
    if arm == FIXED:
        for k in range(plant.steps):
            plant.override = {"setpoint": plant.P["calm"]}
            plant.step()
        plant.finalize()
        return dict(plant.m, writes=0, after_kill_writes=0, restore_ok=True)
    g = None if arm in ("native", FIXED) else Governor()
    if arm == "watch":
        g.set_mode(OBSERVE)
    kill_at = int(KILL_AT * plant.steps)
    writes = after_kill_writes = 0
    last = None
    restore_ok = True
    for k in range(plant.steps):
        if g is not None:
            obs = plant.observe()
            if arm == "omni" and k == kill_at:
                g.kill()
            if knob == "power" and g.has_authority:
                g.current_cap = plant.knob_value("power")
            d = g.step(obs, 0)
            v = _apply(plant, knob, g, d, last)
            if v is not None:
                if last is None or v != last:
                    writes += 1
                last = v
            if arm == "omni" and k >= kill_at:
                after_kill_writes += int(v is not None)
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
def run_organism_arm(rows, seed, arm):
    plants = [make_plant(r, seed, organism=True) for r in rows]
    knobs = [r["knob"] for r in rows]
    zones = [p for p in plants if isinstance(p, ThermalZone)]
    stores = [p for p in plants if isinstance(p, EnergyStorage)]
    sources = [p for p in plants if not isinstance(p, (ThermalZone, EnergyStorage))]
    nom_src = sum(p.nominal_w for p in sources) or 1.0
    nom_sz = nom_src + sum(z.nominal_w for z in zones)
    nom_all = nom_sz + sum(s.nominal_w for s in stores)
    k_heat = [0.3 * z.P["q_it_w"] / (nom_src / len(zones)) for z in zones] if zones else []
    k_load = [0.3 * s.P["load_w"] / (nom_sz / len(stores)) for s in stores] if stores else []
    budget = 1.25 * nom_all
    g = None if arm == "native" else Governor()
    if arm == "watch":
        g.set_mode(OBSERVE)
    kill_at = int(KILL_AT * ORGANISM_STEPS)
    writes = after_kill_writes = 0
    restore_ok = True
    last = [None] * len(plants)
    src_w, sz_w, all_w = nom_src, nom_sz, nom_all
    cap_now = 1.0
    for k in range(ORGANISM_STEPS):
        th = sum(z.zone_thermal() for z in zones) / len(zones) if zones else None
        for z, kh in zip(zones, k_heat):
            z.ext = {"heat_w": kh * src_w / len(zones)}
        for s, kl in zip(stores, k_load):
            s.ext = {"load_w": kl * (sz_w - nom_sz) / len(stores)}
        if th is not None:
            for p in plants:
                if not isinstance(p, ThermalZone):
                    p.ext["thermal"] = th
        if g is not None:
            obs = [p.observe() for p in plants]
            n = len(obs)
            agg = {key: sum(o[key] for o in obs) / n for key in ("queue_ratio", "load_ratio", "network_stress",
                                                               "drift_ratio")}
            agg.update(power_stress=all_w / budget, thermal=max(o["thermal"] for o in obs), stale=0.0,
                       security_block=0.0)
            if arm == "omni" and k == kill_at:
                g.kill()
            g.current_cap = cap_now if g.has_authority else 1.0
            d = g.step(agg, 0)
            if g.has_authority and "power" in knobs:
                cap_now = d["power_cap"]
            for i, (p, knob) in enumerate(zip(plants, knobs)):
                v = _apply(p, knob, g, d, last[i])
                if v is not None:
                    if last[i] is None or v != last[i]:
                        writes += 1
                    last[i] = v
                if arm == "omni" and k >= kill_at:
                    after_kill_writes += int(v is not None)
                    restore_ok = restore_ok and _restored(p, knob)
        for p in plants:
            p.step()
        src_w = sum(p.power_w for p in sources)
        sz_w = src_w + sum(p.power_w for p in zones)
        all_w = sz_w + sum(p.power_w for p in stores)
    for p in plants:
        p.finalize()
    return {"plants": [dict(p.m) for p in plants], "writes": writes, "after_kill_writes": after_kill_writes,
            "restore_ok": restore_ok and after_kill_writes == 0}


def run_organism(rows, seed) -> Dict:
    out = {arm: run_organism_arm(rows, seed, arm) for arm in ARMS}
    out["watch_equal"] = out["watch"]["plants"] == out["native"]["plants"] and out["watch"]["writes"] == 0
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
