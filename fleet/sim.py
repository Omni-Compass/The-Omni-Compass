"""Fleet simulation: arms x vessels at 15-second resolution.

Arms
  k8s_hpa60_ca, k8s_hpa70_ca, k8s_hpa80_ca   HPA at target 0.6 / 0.7 / 0.8 with Cluster Autoscaler
  k8s_hpa70_karpenter                          HPA 0.7 with Karpenter-lite
  omni_observe                                 governor computes every minute, HPA 0.7 + CA act (must equal k8s_hpa70_ca)
  omni_target                                  governor writes the HPA target (rho*) every minute; CA unchanged
  omni_fleet                                   governor is the single node and power authority (fleet-mode law, decisions
                                               every 60 s); HPA runs with target rho*; Cluster Autoscaler is not run;
                                               scheduling floor: never fewer nodes than current pod requests need;
                                               actions pass through the shield (I4 not applied)
  omni_fleet_balanced, omni_fleet_wear         omni_fleet with the equation (2) gate active in both directions
  omni_fleet_park                              omni_fleet (energy-first) with the idle-power path: capacity reductions park
                                               nodes (Ready, park_frac x idle power, wake in one tick) instead of powering
                                               them off; in pools where power-off is not permitted every arm parks
  omni_fleet_no_dynamics                       omni_fleet with equations (1)-(7) not evolved
  omni_fleet_no_gate                           omni_fleet without the equation (2) release gate
Batch and GPU vessels have no HPA; their omni_target arm equals the CA baseline and is omitted.
Every arm uses the same boot delay, plant, power model and scoring.
"""
from __future__ import annotations

import copy, hashlib, math, sys
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fleet.harness import (TICK, STEPS, BOOT_TICKS, Scenario, Cluster, make_scenario, hpa_step)
from omnicompass.adapter import Governor, AllocationLaw, mode_law, OBSERVE, AUTOPILOT
from omnicompass.shield import enforce, ShieldLimits

ALLOC = 0.95
OMNI_EVERY = 4
ARMS_WEB = ["k8s_hpa60_ca", "k8s_hpa70_ca", "k8s_hpa80_ca", "k8s_hpa70_karpenter", "omni_observe", "omni_target",
            "omni_fleet", "omni_fleet_balanced", "omni_fleet_wear", "omni_fleet_park", "omni_fleet_no_dynamics", "omni_fleet_no_gate"]
ARMS_JOB = ["k8s_hpa70_ca", "k8s_hpa70_karpenter", "omni_observe", "omni_fleet", "omni_fleet_balanced", "omni_fleet_wear",
            "omni_fleet_park", "omni_fleet_no_dynamics", "omni_fleet_no_gate"]


def arms_for(vessel):
    return ARMS_WEB if vessel in ("web", "multi") else ARMS_JOB


def hpa_target(arm):
    return {"k8s_hpa60_ca": 0.6, "k8s_hpa80_ca": 0.8}.get(arm, 0.7)


def run(scn0: Scenario, arm: str, law: AllocationLaw = None, omni_every: int = OMNI_EVERY, governor_law: AllocationLaw = None) -> Dict:
    scn = copy.deepcopy(scn0)
    single = arm.startswith("omni_fleet") or arm.startswith("omni_single")
    uses_gov = arm.startswith("omni")
    base_law = law or AllocationLaw()
    fmode = {"omni_fleet_balanced": "fleet_balanced", "omni_fleet_wear": "fleet_wear"}.get(arm, "fleet")
    glaw = governor_law if governor_law is not None else (mode_law(fmode, base_law) if single else base_law)
    if arm == "omni_fleet_no_gate":
        from dataclasses import replace as _r
        glaw = _r(glaw, push_release=9.0)
    if single and governor_law is None:
        omni_every = 4
    lim = ShieldLimits(power_limit=1e9) if single else ShieldLimits()
    govs = [Governor(law=glaw, evolve=arm != "omni_fleet_no_dynamics") for _ in scn.clusters] if uses_gov else []
    for g in govs:
        g.set_mode(AUTOPILOT if arm in ("omni_target",) or single else OBSERVE)
    targets = [hpa_target(arm)] * len(scn.clusters)
    energy = dem = done = 0.0
    viol_q = viol_p = viol_h = healthy = 0
    starts = stops = rev = 0
    last_dir = [0] * len(scn.clusters)
    shield_hits = 0
    park_moves = 0
    site_power = 0.0
    trace = []
    for t in range(STEPS):
        # plant
        site_power = 0.0
        stress_q = []
        for ci, c in enumerate(scn.clusters):
            p = c.pool
            p.booting = [b - 1 for b in p.booting]
            ready_now = sum(1 for b in p.booting if b <= 0)
            p.nodes += ready_now
            p.booting = [b for b in p.booting if b > 0]
            alloc = p.nodes * p.cores * ALLOC
            reqs = 0.0
            for w in c.workloads:
                w.req_now = w.replicas * w.request if w.hpa else w.demand[t] + w.backlog
                reqs += w.req_now
            frac = min(1.0, alloc / reqs) if reqs > 0 else 1.0
            used = 0.0
            cap_rate = 0.0
            for w in c.workloads:
                d = w.demand[t]
                capw = w.req_now * frac * p.cap
                srv = min(d + w.backlog, capw)
                w.backlog = d + w.backlog - srv
                dem += d; done += srv; used += srv; cap_rate += max(capw, 1e-9)
                w.metric_next = min(1.0, srv / max(w.replicas * w.request, 1e-9)) if w.hpa else 0.0
            c.pending = max(0.0, reqs - alloc)
            c.reqs, c.alloc, c.used = reqs, alloc, used
            util = min(1.0, used / max(alloc, 1e-9))
            kw = (p.nodes * p.cap * (p.idle_kw + p.dyn_kw * util) + len(p.booting) * p.idle_kw + p.parked * p.idle_kw * p.park_frac) * scn.pue
            c.kw = kw
            site_power += kw
            c.q = min(2.0, sum(w.backlog for w in c.workloads) / max(cap_rate * 8.0, 1e-9))
            stress_q.append(c.q)
        pstress = site_power / scn.site_limit_kw
        for c in scn.clusters:
            c.pool.thermal = 0.97 * c.pool.thermal + 0.03 * (0.30 + 0.65 * min(1.4, pstress))
        energy += site_power * TICK / 3600.0
        qmax = max(stress_q); th = max(c.pool.thermal for c in scn.clusters)
        viol_q += qmax > 0.35; viol_p += pstress > 1.05; viol_h += th > 1.03
        healthy += (qmax < 0.28 and pstress <= 1.02 and th < 0.96)
        # metrics-server: publish this tick's usage for the next tick
        for c in scn.clusters:
            for w in c.workloads:
                w.metric = w.metric_next
        # governor (every minute)
        if uses_gov and t % omni_every == 0:
            for ci, (c, g) in enumerate(zip(scn.clusters, govs)):
                load = min(2.0, c.used / max(c.alloc * c.pool.cap, 1e-9)) if c.alloc > 0 else 2.0
                obs = {"queue_ratio": c.q, "load_ratio": load, "power_stress": pstress, "thermal": c.pool.thermal,
                       "network_stress": 0.0, "drift_ratio": 0.0, "stale": 0.0, "security_block": 0.0}
                g.current_cap = c.pool.cap
                g.nodes = c.pool.nodes + len(c.pool.booting)
                d = g.step(obs, 0)
                if not g.has_authority:
                    continue
                targets[ci] = min(0.95, max(0.5, float(d["demand"])))
                if single:
                    p = c.pool
                    n = p.nodes + len(p.booting)
                    fit = int(math.ceil(c.reqs / (p.cores * ALLOC))) if c.reqs > 0 else p.min_nodes
                    tgt = max(p.min_nodes, min(p.max_nodes, max(n + int(d["node_delta"]), fit)))
                    acts = []
                    if tgt != n:
                        acts.append({"action": "nodes", "target": tgt, "direction": 1 if tgt > n else -1})
                    if abs(d["power_cap"] - p.cap) > 1e-9:
                        acts.append({"action": "power_cap", "target": d["power_cap"], "direction": -1 if d["power_cap"] < p.cap else 1})
                    cfg = SimpleNamespace(minimum_nodes=p.min_nodes, maximum_nodes=p.max_nodes)
                    acts, h = enforce(acts, {"actual_nodes": n, "power_cap": p.cap}, obs, cfg, lim)
                    shield_hits += h
                    for a in acts:
                        if a["action"] == "nodes":
                            _resize(c, int(a["target"]), park=(arm == "omni_fleet_park" or not p.power_off))
                        elif a["action"] == "power_cap":
                            p.cap = float(a["target"])
        # HPA (every tick) and node controller
        for ci, c in enumerate(scn.clusters):
            for w in c.workloads:
                if w.hpa:
                    hpa_step(w, targets[ci])
            n_before = c.pool.nodes + len(c.pool.booting)
            parked_before = c.pool.parked
            if not single:
                if arm == "k8s_hpa70_karpenter":
                    _karpenter(c, t)
                else:
                    _cluster_autoscaler(c)
            n_after = c.pool.nodes + len(c.pool.booting)
            dpark = c.pool.parked - parked_before
            dn = n_after - n_before + dpark
            park_moves += abs(dpark)
            if single and hasattr(c, "_single_dn"):
                dn += c._single_dn; c._single_dn = 0
            park_moves += getattr(c, "_park_moves", 0); c._park_moves = 0
            starts += max(0, dn); stops += max(0, -dn)
            if dn:
                dr = 1 if dn > 0 else -1
                rev += int(last_dir[ci] != 0 and dr != last_dir[ci]); last_dir[ci] = dr
        if t % 40 == 0:
            trace.append(tuple((c.pool.nodes, len(c.pool.booting), round(c.pool.cap, 9), tuple(w.replicas for w in c.workloads)) for c in scn.clusters))
    return {"vessel": scn.vessel, "seed": scn.seed, "arm": arm, "energy_kwh": energy, "work_completed": done / max(dem, 1e-9),
            "time_healthy": healthy / STEPS, "violation_backlog": viol_q / STEPS, "violation_power": viol_p / STEPS,
            "violation_heat": viol_h / STEPS, "machines_started": starts, "machines_stopped": stops,
            "node_reversals": rev, "shield_interventions": shield_hits, "park_moves": park_moves,
            "trace_hash": hashlib.sha256(repr(trace).encode()).hexdigest()[:16]}


def _resize(c: Cluster, tgt: int, park: bool = False) -> None:
    p = c.pool
    n = p.nodes + len(p.booting)
    dn = tgt - n
    boots = offs = moves = 0
    if dn > 0:
        wake = min(dn, p.parked); p.parked -= wake; p.nodes += wake; moves += wake
        boots = dn - wake
        p.booting += [BOOT_TICKS] * boots
    elif dn < 0:
        k = -dn
        cancel = min(k, len(p.booting)); p.booting = p.booting[cancel:]; k -= cancel; offs += cancel
        k = min(k, max(0, p.nodes - p.min_nodes))
        if park:
            p.nodes -= k; p.parked += k; moves += k
        else:
            p.nodes -= k; offs += k
    c._single_dn = getattr(c, "_single_dn", 0) + boots - offs
    c._park_moves = getattr(c, "_park_moves", 0) + moves


def _cluster_autoscaler(c: Cluster) -> None:
    p = c.pool
    c.ca_since_add += 1
    if c.pending > 0:
        need = int(math.ceil(c.pending / (p.cores * ALLOC))) - len(p.booting)
        if need > 0:
            wake = min(need, p.parked); p.parked -= wake; p.nodes += wake; need -= wake
            add = min(need, p.max_nodes - p.nodes - len(p.booting) - p.parked)
            if add > 0:
                p.booting += [BOOT_TICKS] * add
            if add > 0 or wake > 0:
                c.ca_since_add = 0
        c.ca_under = 0
        return
    ru = c.reqs / max(c.alloc, 1e-9)
    c.ca_under = c.ca_under + 1 if ru < 0.5 else 0
    if c.ca_under * TICK >= 600 and c.ca_since_add * TICK >= 600 and p.nodes > p.min_nodes and not p.booting:
        if p.power_off:
            p.nodes -= 1
        else:
            p.nodes -= 1; p.parked += 1
        c.ca_under = 0


def _karpenter(c: Cluster, t: int) -> None:
    p = c.pool
    if c.pending > 0:
        need = max(0, int(math.ceil(c.pending / (p.cores * ALLOC))) - len(p.booting))
        wake = min(need, p.parked); p.parked -= wake; p.nodes += wake; need -= wake
        add = min(need, p.max_nodes - p.nodes - len(p.booting) - p.parked)
        if add > 0:
            p.booting += [BOOT_TICKS] * add
        return
    if t % 2 == 0 and p.nodes > p.min_nodes and not p.booting and c.reqs <= 0.9 * (p.nodes - 1) * p.cores * ALLOC:
        p.nodes -= 1
        if not p.power_off:
            p.parked += 1
