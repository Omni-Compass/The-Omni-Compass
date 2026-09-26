"""Fleet simulation with a response-time gauge and a response-time nerve (speed-first mode).

fleet/sim.py is frozen by results/fleet/PREREGISTRATION.json and has no response-time gauge: its scoring checks that
work finishes and backlog stays small, but never how long a request waits. This module runs the same plant, the same
HPA, Cluster Autoscaler and Karpenter-lite, the same boot delay and power model, and adds:

  response time   per workload and tick, R = S + Wq + W_backlog, where
                  S = S0 / cap                        service time (a power cap slows the CPU)
                  Wq = S * u^(sqrt(2(c+1)) - 1) / (c (1 - u))   queueing delay, Sakasegawa's M/M/c approximation,
                                                      c = scheduled pods, u = demand / scheduled capacity (<= 0.99)
                  W_backlog = backlog / capacity * TICK      time to drain work already waiting
                  S0 = 100 ms. Gauges: demand-weighted p95, p99 and mean over every (tick, workload).
                  Job vessels (batch, gpu) have no request queue: R = S + W_backlog (job wait).
  latency nerve   (omni arms, when lat_gain > 0) the governor's queue observation becomes
                  max(queue, lat_gain * max(0, R_recent / (slo_mult * S0) - 1)), R_recent = worst demand-weighted
                  response time over the ticks since the last decision. The engine equations are unchanged.

Arm names and behaviour are those of fleet/sim.py; k8s_hpa50_ca (HPA target 0.5) is added because 50% is the
target of the live lab workload. With lat_gain = 0 and the frozen fleet law, omni_fleet here reproduces the
frozen omni_fleet trace (checked by tests/test_sim_slo.py).
"""
from __future__ import annotations

import copy, hashlib, math, sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Dict

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fleet.harness import TICK, STEPS, Scenario, hpa_step
from fleet.sim import ALLOC, OMNI_EVERY, _resize, _cluster_autoscaler, _karpenter
from omnicompass.adapter import Governor, AllocationLaw, mode_law, OBSERVE, AUTOPILOT
from omnicompass.shield import enforce, ShieldLimits
from omnicompass.speed import SpeedGovernor, SpeedLaw
from omnicompass.mathdrive import MathDrive, MathLaw

S0_MS = 100.0
REC = None   # when a list, run() appends each tick's per-cluster pod requests (analysis only)


# Vendor opponents: emulations of documented behaviour (not the vendors' binaries). Declared parameters:
#   openshift      OpenShift ClusterAutoscaler resource, documented example values: utilizationThreshold 0.4,
#                  unneededTime 5m, delayAfterAdd 10m (HPA 0.7 on the workloads)
#   gke_balanced   GKE default profile = upstream Cluster Autoscaler (0.5, 10 min): identical to k8s_hpa70_ca
#   gke_optimize   GKE optimize-utilization: MostAllocated packing and more aggressive scale-down. GKE publishes no
#                  numbers; declared here as threshold 0.65 (packing lets more nodes qualify) and unneeded time 2 min
#   aks_nap        AKS node auto-provisioning = Karpenter, WhenEmptyOrUnderutilized, consolidateAfter 0s: identical
#                  to k8s_hpa70_karpenter
#   turbonomic     IBM Turbonomic: container requests resized every 10 min to the p99 of per-pod usage (its default
#                  aggressiveness) over the run so far, one step of at most 50%; nodes suspended/provisioned toward
#                  a 0.7 packing target (Karpenter-style), HPA 0.7 left in place
#   cast_ai        CAST AI Evictor: every 60 s, a node active for more than 5 minutes is drained and deleted when its
#                  pods fit on the remaining capacity (bin-packing); pending pods add nodes at once
#   spot_ocean     Spot Ocean (NetApp/Flexera): automatic headroom of 5% of requested resources kept as spare
#                  capacity; every minute the least-utilised node is scaled down when its pods fit elsewhere with the
#                  headroom kept
CA_PROFILES = {"openshift": (0.4, 20, 40), "gke_optimize": (0.65, 8, 40)}
VENDOR_ARMS = ["openshift", "gke_balanced", "gke_optimize", "aks_nap", "turbonomic", "cast_ai", "spot_ocean"]


def _add_for_pending(c, extra=0.0):
    import math as _m
    p = c.pool
    need_cores = c.pending + extra
    if need_cores > 0:
        need = max(0, int(_m.ceil(need_cores / (p.cores * ALLOC))) - len(p.booting))
        wake = min(need, p.parked); p.parked -= wake; p.nodes += wake; need -= wake
        add = min(need, p.max_nodes - p.nodes - len(p.booting) - p.parked)
        if add > 0:
            p.booting += [6] * add
            c.last_add = 0
        return True
    return False


def _cast_ai(c, t):
    p = c.pool
    c.last_add = getattr(c, "last_add", 99) + 1
    if _add_for_pending(c):
        return
    if t % 4 == 0 and c.last_add >= 20 and p.nodes > p.min_nodes and not p.booting and c.reqs <= (p.nodes - 1) * p.cores * ALLOC:
        p.nodes -= 1
        if not p.power_off:
            p.parked += 1


def _spot_ocean(c, t):
    p = c.pool
    c.last_add = getattr(c, "last_add", 99) + 1
    spare = p.nodes * p.cores * ALLOC - c.reqs + len(p.booting) * p.cores * ALLOC
    short = max(0.0, 0.05 * c.reqs - spare) if c.pending <= 0 else 0.0
    if _add_for_pending(c, short):
        return
    if t % 4 == 0 and p.nodes > p.min_nodes and not p.booting and 1.05 * c.reqs <= (p.nodes - 1) * p.cores * ALLOC:
        p.nodes -= 1
        if not p.power_off:
            p.parked += 1


def _ca_profile(c, thr, unneeded, after_add):
    """Upstream Cluster Autoscaler logic with a profile's threshold and timers (ticks of 15 s)."""
    import math as _m
    p = c.pool
    c.ca_since_add += 1
    if c.pending > 0:
        need = int(_m.ceil(c.pending / (p.cores * ALLOC))) - len(p.booting)
        if need > 0:
            wake = min(need, p.parked); p.parked -= wake; p.nodes += wake; need -= wake
            add = min(need, p.max_nodes - p.nodes - len(p.booting) - p.parked)
            if add > 0:
                p.booting += [6] * add
            if add > 0 or wake > 0:
                c.ca_since_add = 0
        c.ca_under = 0
        return
    ru = c.reqs / max(c.alloc, 1e-9)
    c.ca_under = c.ca_under + 1 if ru < thr else 0
    if c.ca_under >= unneeded and c.ca_since_add >= after_add and p.nodes > p.min_nodes and not p.booting:
        p.nodes -= 1
        if not p.power_off:
            p.parked += 1
        c.ca_under = 0


def _turbo_nodes(c, t):
    import math as _m
    p = c.pool
    if c.pending > 0:
        need = max(0, int(_m.ceil(c.pending / (p.cores * ALLOC))) - len(p.booting))
        wake = min(need, p.parked); p.parked -= wake; p.nodes += wake; need -= wake
        add = min(need, p.max_nodes - p.nodes - len(p.booting) - p.parked)
        if add > 0:
            p.booting += [6] * add
        return
    if t % 4 == 0 and p.nodes > p.min_nodes and not p.booting and c.reqs <= 0.7 * (p.nodes - 1) * p.cores * ALLOC:
        p.nodes -= 1
        if not p.power_off:
            p.parked += 1


@dataclass(frozen=True)
class DirectLaw:
    """Architecture C, strict: Kubernetes keeps only its muscle (scheduler places pods, kubelet runs them); the HPA,
    Cluster Autoscaler, VPA and Karpenter are off. Omni-Compass sets every workload's replica count itself:
      up     at once to ceil(replicas x usage / rho* + kb x backlog / request)   (no HPA tolerance band or rate limit)
      down   to the highest recommendation of the last `window` ticks, only while the engine's push <= push_release
    rho* is the engine's target (the speed law's), machines follow the speed law."""
    window: int = 20
    kb: float = 1.0
    push_release: float = 0.05
    tol: float = 0.0


def omni_replicas(w, rho, push, L):
    import math as _m
    cur = w.replicas
    want = max(w.min_rep, min(w.max_rep, int(_m.ceil(cur * w.metric / max(rho, 1e-9) + L.kb * w.backlog / max(w.request, 1e-9) - 1e-9))))
    if abs(w.metric / max(rho, 1e-9) - 1.0) <= L.tol and w.backlog <= 1e-9:
        want = cur
    w.rec_hist = (w.rec_hist + [want])[-max(1, L.window):]
    if want > cur:
        w.replicas = want
    elif want < cur and push <= L.push_release:
        w.replicas = max(w.min_rep, max(w.rec_hist))


@dataclass(frozen=True)
class BLaw:
    """Architecture B (Omni-Compass on top of a platform). The platform's own controllers run unchanged; Omni-Compass
    intervenes only in two ways, each gated by the engine:
      veto   a node removal the platform just made is undone while requests are rising (trend over `lag` ticks above
             `rise`) or the engine has not converged (push > push_hold) or unrelieved need I_U > need_hold: a removal
             that would be reversed within the boot delay costs a stop, a start, a boot and pending pods
      early  one node is added ahead when the requests projected `lead` ticks ahead exceed allocatable capacity and no
             node is booting: the node the platform would add after pods go pending, added before they do
      flip   a removal within flip_guard ticks of the platform's own last addition is undone (flip-flop damping)
    Pods, HPA targets and everything else stay the platform's."""
    lag: int = 8
    rise: float = 0.02
    push_hold: float = 9.0
    need_hold: float = 9.0
    lead: int = 6
    early: bool = True
    veto: bool = True
    flip_guard: int = 0         # veto a removal within this many ticks of the platform's last addition (0 = off)
    confirm: int = 1            # early add only after the rise has been seen this many consecutive ticks


def _omni_on_top(c, before, g, L):
    import math as _m
    p = c.pool
    h = getattr(c, "_rh", []); h.append(c.reqs); c._rh = h[-64:]
    c._tick = getattr(c, "_tick", 0) + 1
    trend = (h[-1] - h[-1 - L.lag]) / max(h[-1 - L.lag], 1e-9) if len(h) > L.lag else 0.0
    veto = early = 0
    n0, parked0, boot0 = before
    delta = (p.nodes + len(p.booting)) - (n0 + len(boot0))
    if delta > 0:
        c._last_add = c._tick
    removed = -delta
    recent = L.flip_guard > 0 and c._tick - getattr(c, "_last_add", -10 ** 9) <= L.flip_guard
    if removed > 0 and ((L.veto and (trend > L.rise or g.last_push > L.push_hold or g.x.I_U > L.need_hold)) or recent):
        p.nodes, p.parked, p.booting = n0, parked0, list(boot0)
        veto = 1
    c._rise = getattr(c, "_rise", 0) + 1 if len(h) > L.lag and h[-1] > h[-1 - L.lag] else 0
    if L.early and not p.booting and len(h) > L.lag and c._rise >= L.confirm:
        slope = (h[-1] - h[-1 - L.lag]) / L.lag
        if slope > 0 and h[-1] + slope * L.lead > p.nodes * p.cores * ALLOC and p.nodes + p.parked < p.max_nodes:
            if p.parked:
                p.parked -= 1; p.nodes += 1
            else:
                p.booting.append(6)
            early = 1
    return veto, early


def hpa_target(arm):
    return {"k8s_hpa50_ca": 0.5, "k8s_hpa60_ca": 0.6, "k8s_hpa80_ca": 0.8}.get(arm, 0.7)


def response_ms(w, d, capw, cap, frac):
    s = S0_MS / max(cap, 1e-9)
    drain = (w.backlog / max(capw, 1e-9)) * TICK * 1000.0 if w.backlog > 1e-12 else 0.0
    if not w.hpa:
        return s + drain
    c = max(1.0, w.replicas * frac)
    u = min(0.99, d / max(capw, 1e-9))
    wq = s * u ** (math.sqrt(2.0 * (c + 1.0)) - 1.0) / (c * (1.0 - u)) if u > 0 else 0.0
    return s + wq + drain


def wpct(vals, wts, q):
    v = np.asarray(vals); wt = np.asarray(wts)
    if wt.sum() <= 0:
        return float(np.percentile(v, q)) if len(v) else 0.0
    o = np.argsort(v); v, wt = v[o], wt[o]
    cw = np.cumsum(wt) / wt.sum()
    return float(v[min(len(v) - 1, np.searchsorted(cw, q / 100.0))])


def run(scn0: Scenario, arm: str, governor_law: AllocationLaw = None, omni_every: int = OMNI_EVERY,
        lat_gain: float = 0.0, slo_mult: float = 2.0, speed_law: SpeedLaw = None, math_law: MathLaw = None, b_law: "BLaw" = None, direct_law: "DirectLaw" = None) -> Dict:
    scn = copy.deepcopy(scn0)
    on_top = arm.startswith("omniB:")          # architecture B: a platform runs, Omni-Compass governs on top of it
    base = arm.split(":", 1)[1] if on_top else arm
    mathd = arm == "omni_math"
    direct = arm == "omni_direct"
    DL = direct_law or DirectLaw()
    speed = arm == "omni_speed" or mathd or direct
    single = arm.startswith("omni_fleet") or arm.startswith("omni_single") or speed
    uses_gov = arm.startswith("omni")
    B = b_law or BLaw()
    glaw = governor_law if governor_law is not None else (mode_law("fleet", AllocationLaw()) if single else AllocationLaw())
    if single and governor_law is None and not speed:
        omni_every = 4
    lim = ShieldLimits(power_limit=1e9) if single else ShieldLimits()
    govs = [Governor(law=glaw) for _ in scn.clusters] if uses_gov and not speed else []
    for g in govs:
        g.set_mode(AUTOPILOT if single or arm == "omni_target" else OBSERVE)
    b_veto = b_early = 0
    if speed:
        govs = [MathDrive(math_law or MathLaw()) if mathd else SpeedGovernor(speed_law or SpeedLaw()) for _ in scn.clusters]
    targets = [hpa_target(base)] * len(scn.clusters)
    energy = dem = done = 0.0
    viol_q = viol_p = viol_h = healthy = 0
    starts = stops = rev = 0
    last_dir = [0] * len(scn.clusters)
    node_ticks = 0
    pod_changes = 0
    cap_moves = 0
    R_all, W_all = [], []
    r_recent = [0.0] * len(scn.clusters)
    trace = []
    for t in range(STEPS):
        site_power = 0.0
        stress_q = []
        for ci, c in enumerate(scn.clusters):
            p = c.pool
            p.booting = [b - 1 for b in p.booting]
            p.nodes += sum(1 for b in p.booting if b <= 0)
            p.booting = [b for b in p.booting if b > 0]
            alloc = p.nodes * p.cores * ALLOC
            reqs = 0.0
            for w in c.workloads:
                w.req_now = w.replicas * w.request if w.hpa else w.demand[t] + w.backlog
                reqs += w.req_now
            frac = min(1.0, alloc / reqs) if reqs > 0 else 1.0
            used = cap_rate = 0.0
            rs, ws = [], []
            for w in c.workloads:
                d = w.demand[t]
                capw = w.req_now * frac * p.cap
                srv = min(d + w.backlog, capw)
                w.backlog = d + w.backlog - srv
                dem += d; done += srv; used += srv; cap_rate += max(capw, 1e-9)
                w.metric_next = min(1.0, srv / max(w.replicas * w.request, 1e-9)) if w.hpa else 0.0
                if base == "turbonomic" and w.hpa:
                    w.use_hist = getattr(w, "use_hist", []) + [srv / max(1, w.replicas)]
                if d > 0:
                    r = response_ms(w, d, capw, p.cap, frac)
                    rs.append(r); ws.append(d)
            R_all += rs; W_all += ws
            rc = float(np.average(rs, weights=ws)) if ws else S0_MS
            r_recent[ci] = max(r_recent[ci], rc)
            c.pending = max(0.0, reqs - alloc)
            c.reqs, c.alloc, c.used = reqs, alloc, used
            util = min(1.0, used / max(alloc, 1e-9))
            kw = (p.nodes * p.cap * (p.idle_kw + p.dyn_kw * util) + len(p.booting) * p.idle_kw
                  + p.parked * p.idle_kw * p.park_frac) * scn.pue
            c.kw = kw
            site_power += kw
            node_ticks += p.nodes + len(p.booting)
            c.q = min(2.0, sum(w.backlog for w in c.workloads) / max(cap_rate * 8.0, 1e-9))
            stress_q.append(c.q)
        if REC is not None:
            REC.append([c.reqs for c in scn.clusters])
        pstress = site_power / scn.site_limit_kw
        for c in scn.clusters:
            c.pool.thermal = 0.97 * c.pool.thermal + 0.03 * (0.30 + 0.65 * min(1.4, pstress))
        energy += site_power * TICK / 3600.0
        qmax = max(stress_q); th = max(c.pool.thermal for c in scn.clusters)
        viol_q += qmax > 0.35; viol_p += pstress > 1.05; viol_h += th > 1.03
        healthy += (qmax < 0.28 and pstress <= 1.02 and th < 0.96)
        for c in scn.clusters:
            for w in c.workloads:
                w.metric = w.metric_next
        if uses_gov and t % omni_every == 0:
            for ci, (c, g) in enumerate(zip(scn.clusters, govs)):
                load = min(2.0, c.used / max(c.alloc * c.pool.cap, 1e-9)) if c.alloc > 0 else 2.0
                q = c.q
                if lat_gain > 0:
                    q = max(q, min(2.0, lat_gain * max(0.0, r_recent[ci] / (slo_mult * S0_MS) - 1.0)))
                r_recent[ci] = 0.0
                obs = {"queue_ratio": q, "load_ratio": load, "power_stress": pstress, "thermal": c.pool.thermal,
                       "network_stress": 0.0, "drift_ratio": 0.0, "stale": 0.0, "security_block": 0.0}
                if speed:
                    p = c.pool
                    n = p.nodes + len(p.booting)
                    if mathd:
                        rho, tgt, capn, _ = g.step(obs, n, c.reqs, p.cores * ALLOC)
                    else:
                        g.g.current_cap = p.cap
                        rho, tgt, capn = g.step(obs, n, c.reqs, p.cores * ALLOC)
                    targets[ci] = min(0.95, max(0.4, rho))
                    tgt = max(p.min_nodes, min(p.max_nodes, tgt))
                    if tgt != n:
                        _resize(c, tgt, park=not p.power_off)
                    if abs(capn - p.cap) > 1e-9:
                        p.cap = capn; cap_moves += 1
                    continue
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
                    acts, _ = enforce(acts, {"actual_nodes": n, "power_cap": p.cap}, obs, cfg, lim)
                    for a in acts:
                        if a["action"] == "nodes":
                            _resize(c, int(a["target"]), park=(arm == "omni_fleet_park" or not p.power_off))
                        elif a["action"] == "power_cap":
                            p.cap = float(a["target"]); cap_moves += 1
        for ci, c in enumerate(scn.clusters):
            for w in c.workloads:
                if w.hpa:
                    before = w.replicas
                    if direct:
                        omni_replicas(w, targets[ci], govs[ci].g.last_push, DL)
                    else:
                        hpa_step(w, targets[ci])
                    pod_changes += abs(w.replicas - before)
            n_before = c.pool.nodes + len(c.pool.booting)
            parked_before = c.pool.parked
            if not single:
                pb = (c.pool.nodes, c.pool.parked, list(c.pool.booting))
                if base in ("k8s_hpa70_karpenter", "aks_nap"):
                    _karpenter(c, t)
                elif base in CA_PROFILES:
                    _ca_profile(c, *CA_PROFILES[base])
                elif base == "cast_ai":
                    _cast_ai(c, t)
                elif base == "spot_ocean":
                    _spot_ocean(c, t)
                elif base == "turbonomic":
                    _turbo_nodes(c, t)
                    if t % 40 == 39:
                        for w in c.workloads:
                            if w.hpa and getattr(w, "use_hist", None):
                                want = max(0.05, float(np.percentile(w.use_hist, 99)))
                                w.request = float(min(w.request * 1.5, max(w.request * 0.5, want)))
                else:
                    _cluster_autoscaler(c)
                if on_top:
                    v, e = _omni_on_top(c, pb, govs[ci], B)
                    b_veto += v; b_early += e
            n_after = c.pool.nodes + len(c.pool.booting)
            dn = n_after - n_before + (c.pool.parked - parked_before)
            if single and hasattr(c, "_single_dn"):
                dn += c._single_dn; c._single_dn = 0
            c._park_moves = 0
            starts += max(0, dn); stops += max(0, -dn)
            if dn:
                dr = 1 if dn > 0 else -1
                rev += int(last_dir[ci] != 0 and dr != last_dir[ci]); last_dir[ci] = dr
        if t % 40 == 0:
            trace.append(tuple((c.pool.nodes, len(c.pool.booting), round(c.pool.cap, 9), tuple(w.replicas for w in c.workloads)) for c in scn.clusters))
    return {"vessel": scn.vessel, "seed": scn.seed, "arm": arm, "energy_kwh": energy, "work_completed": done / max(dem, 1e-9),
            "time_healthy": healthy / STEPS, "violation_backlog": viol_q / STEPS, "violation_power": viol_p / STEPS,
            "violation_heat": viol_h / STEPS, "machines_started": starts, "machines_stopped": stops,
            "node_reversals": rev, "node_hours": node_ticks * TICK / 3600.0, "pod_changes": pod_changes,
            "cap_moves": cap_moves, "b_vetoes": b_veto, "b_early_adds": b_early, "p95_ms": wpct(R_all, W_all, 95), "p99_ms": wpct(R_all, W_all, 99),
            "mean_ms": float(np.average(R_all, weights=W_all)) if W_all else S0_MS,
            "trace_hash": hashlib.sha256(repr(trace).encode()).hexdigest()[:16]}
