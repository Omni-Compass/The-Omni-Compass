"""Realm plants: the machines the 656 muscles act on (evidence class S: declared models, not meters).

Five plant models. Each one carries its own native controller and runs correctly with no Omni at all:

  compute_pool    servers, nodes, GPUs, robots, radio cells or workers serving a request stream; native: the Kubernetes
                  HPA rule (desired = ceil(n * utilisation / target), 10% tolerance, scale-down stabilisation window,
                  start-up delay), a fixed admission limit, full clock
  thermal_zone    a data hall or building zone cooled by staged units; native: PI on a fixed setpoint, units staged to
                  the load, chiller COP from supply and outdoor temperature
  energy_storage  a site with load, solar and a battery behind a grid connection; native: self-consumption above a
                  fixed reserve
  motion_axis     a joint, flight axis, spacecraft axis or vehicle doing point-to-point moves from a task queue;
                  native: PID with feedforward at full speed, motor heating and derating
  process_loop    a first-order process with dead time (level, pressure, chamber temperature, feeder voltage);
                  native: PI on a fixed setpoint, pump or heater power from the actuator

A muscle is one knob of one plant. Omni may hold that knob and only that one; the native controller keeps the rest.
Omni commands a knob the way the shipped controller commands its organs (omni_controller/controller.py,
omni_controller/muscles.py), through the nervous system's authority (omnicompass/nervous_system.py, from_governor):

  expand     adding capacity, performance or protection is always allowed (except during a security hold)
  contract   giving any of it back (fewer machines, a lower speed or power limit, a warmer setpoint, a lower reserve
             of protection) only while the organ has contraction authority (calm >= the organ's threshold, senses live)
             and the plant's service has been clean for the last three decisions (the SLO reflex); continuous organs
             shed at most the calm fraction of their surplus per decision, discrete organs one unit, through a release
             gate (nothing waiting, and after the release the rest runs at or under the engine's utilisation target)
  fail up    while service is breached, the knob returns to the native controller at once
  pacing     admission muscles are batch pacing (the live batch_pace muscle): one muscle's work suspended per decision
             while power stress >= 0.95 or heat >= 0.96 or the nervous system calls a pause; one resumed per decision
             once power stress <= 0.8 and heat < 0.90 (realms/harness.py, pace)

By plant and knob:
  compute_pool  replicas and HPA-type knobs: the HPA target written as min(rho*, the operator's target), never tighter,
                held for one autoscaler window (the live controller's rule); machine pools (Cluster Autoscaler native):
                the node release gate; power: the GPU or CPU-frequency envelope, never under the work's draw plus 30%,
                and never on a request-served pool (the live controller: throttling it saves no energy, only adds
                wait); admission: batch pacing of pausable work only (request traffic is never paused)
  thermal_zone  setpoint: the live cooling law (warm while cool, cold as heat rises, inside [stress, stress + band x
                calm]); units: the release gate; power: the site power envelope above the load plus 10%; admission:
                paced, the migratable 10% is shed
  energy_storage reserve by power stress (released under stress, held when calm only with authority); peak-shave
                ceiling at rho* of the connection (expand only); battery power: the site power envelope; admission:
                paced, the flexible share is deferred; resumed, it is caught up
  motion_axis   speed: up at once to demand, down by the calm share of the surplus; effort: the power envelope;
                admission: paced, no new move starts
  process_loop  setpoint: toward the efficient end of its band by the calm share; actuator range: as motion speed;
                power: the site power envelope above use plus 10%; admission: paced, 10% is shed

Every disturbance trace is drawn from the seed when the plant is built, so all arms of a seed see the same ones.
Meters (work, energy_j, viol, steps) are kept by the plant from its own state; Omni never supplies them.
"""
from __future__ import annotations

import math
import random
from typing import Dict, Optional

KNOBS = ("capacity", "setpoint", "power", "admission")


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def rho_of(d):
    """The engine's utilisation target as the live controller reads it."""
    return clamp(float(d["demand"]), 0.5, 0.95)


def organ(auth, name):
    return auth["organs"].get(name, {}) if auth and auth.get("execute") else {}


def may_contract(auth, name, clean):
    return bool(organ(auth, name).get("contract")) and clean


def calm_of(auth):
    return auth["scalars"]["calm"] if auth and "scalars" in auth else 0.0


def envelope_cap(auth, name, d, floor):
    """A power-type limit inside the organ's envelope, never under the floor (what the work draws plus headroom)."""
    lo, hi = organ(auth, name)["envelope"]
    return clamp(max(clamp(float(d["power_cap"]), lo, hi), floor), lo, 1.0)


def continuous_capacity(x, load, rho, auth, organ_name, clean, lo):
    """Up at once to x * load / rho*; down only with contraction authority, by the calm share of the surplus."""
    req = x * clamp(load, 0.0, 2.0) / rho
    if req > x:
        return min(1.0, req)
    if may_contract(auth, organ_name, clean):
        return max(lo, x - calm_of(auth) * (x - req))
    return x


def ar_trace(rng, n, rho, sd):
    z, out = 0.0, []
    for _ in range(n):
        z = rho * z + rng.gauss(0.0, sd)
        out.append(z)
    return out


class Plant:
    template = ""

    def __init__(self, P: dict, seed: int, steps: int):
        self.P = dict(P)
        self.rng = random.Random(seed)
        self.steps = steps
        self.k = 0
        self.override: Dict[str, float] = {}
        self.ext: Dict[str, float] = {}
        self.m = {"work": 0.0, "energy_j": 0.0, "viol": 0, "steps": 0}
        self.power_w = 0.0
        self.vhist = []
        self.paced = False          # an admission muscle's work suspended by batch pacing (set by the harness)

    def record(self, violated):
        self.m["viol"] += int(violated)
        self.vhist = (self.vhist + [bool(violated)])[-3:]

    @property
    def slo_clean(self):
        """No violation in the last three decisions (the live controller's --slo-clear 3)."""
        return not any(self.vhist)

    def omni_override(self, knob, d, g, auth):
        """The plant's override for this period from the directive d and the nervous system's authority; {} is native."""
        raise NotImplementedError

    def fixed_calm(self):
        """The descriptive comparator for setpoint muscles: the setpoint fixed at its band's calm end, no governor."""
        return {"target" if self.template == "compute_pool" else "setpoint": self.P["calm"]}

    def thermal_obs(self, own):
        return self.ext.get("thermal", own)

    def finalize(self):
        pass


# ---------------------------------------------------------------------------------------------------------------
class ComputePool(Plant):
    template = "compute_pool"

    def __init__(self, P, seed, steps):
        super().__init__(P, seed, steps)
        P, r = self.P, self.rng
        noise = ar_trace(r, steps, 0.9, P["noise"])
        phase = r.uniform(0.0, 2.0 * math.pi)
        self.lam, left, amp = [], 0, 0.0
        for k in range(steps):
            if left == 0 and r.random() < P["burst_p"]:
                left, amp = r.randint(4, 20), r.uniform(0.3, P["burst_max"])
            b = amp if left > 0 else 0.0
            left = max(0, left - 1)
            day = 1.0 + P["diurnal"] * math.sin(2.0 * math.pi * k / P["period_steps"] + phase)
            self.lam.append(max(0.0, P["lam0"] * day * (1.0 + b) * math.exp(noise[k])))
        self.n = int(P["n0"])
        self.pending = []
        self.Q = 0.0
        self.util, self.W, self.drift, self.cap = 0.5, 0.0, 0.0, 1.0
        self.hist = []
        self.th = 0.32
        self.H = 0.0
        self.drop_share = 0.0
        self.unneeded = 0
        self.omni_t, self.omni_t_k = None, 0
        self.nominal_w = P["lam0"] / (P["mu"] * P["target"]) * (P["p_idle"] + P["target"] * P["p_dyn"])
        self.budget_w = 1.5 * self.nominal_w

    def mu(self, cap):
        return self.P["mu"] * cap ** 0.4          # dynamic power ~ f^2.5, so throughput ~ (power share)^0.4

    def omni_override(self, knob, d, g, auth):
        P, clean, rho = self.P, self.slo_clean, rho_of(d)
        if knob == "power":
            org = P.get("power_organ")
            if not org or not may_contract(auth, org, clean):
                return {}                                          # full power: native (and never on a request pool)
            return {"power": envelope_cap(auth, org, d, min(1.0, self.cap * self.util * 1.3))}
        if knob == "admission":
            if not P.get("pausable"):
                return {}                                          # request traffic is never paused (live: pausable jobs only)
            return {"admission": 0.0} if self.paced else {}
        if P.get("ca"):                                            # a machine pool: the node release gate
            n = self.n
            ok = (may_contract(auth, "nodes", clean) and n > P["n_min"] and not self.pending and self.Q <= 0.0
                  and self.util * n / (n - 1) <= rho)
            return {"release": 1.0} if ok else {}
        # pods: the HPA target, never tighter than the operator's, held for one autoscaler window
        want = min(rho, P["target"]) if clean else P["target"]
        if self.omni_t is None or not clean or self.k - self.omni_t_k >= P["stab_steps"]:
            self.omni_t, self.omni_t_k = want, self.k
        return {"target": self.omni_t}

    def observe(self):
        P = self.P
        pw = self.power_w / self.budget_w
        latency_pressure = max(0.0, self.W / P["slo_s"] - 1.0, self.drop_share)
        return {"queue_ratio": min(2.0, max(len(self.pending) / max(1, self.n), latency_pressure)),
                "load_ratio": self.util, "power_stress": pw, "thermal": self.thermal_obs(self.th),
                "network_stress": self.util if P.get("network") else 0.0, "drift_ratio": self.drift,
                "stale": 0.0, "security_block": 0.0}

    def hpa(self, util):
        target = self.override.get("target", self.P["target"])
        cur = self.n + len(self.pending)
        ratio = util / target
        rec = cur if abs(ratio - 1.0) <= 0.1 else math.ceil(self.n * ratio)
        self.hist.append(rec)
        self.hist = self.hist[-self.P["stab_steps"]:]
        return rec if rec >= cur else min(cur, max(self.hist))

    def cluster_autoscaler(self, util, mu):
        """Native machine pool: add machines while work is waiting; remove one after it has been unneeded (the rest
        under 50% utilised) for the unneeded time (Cluster Autoscaler defaults: 0.5, 10 minutes)."""
        P = self.P
        total = self.n + len(self.pending)
        if self.Q > 0.0 and util >= 0.99:
            self.unneeded = 0
            return max(total, math.ceil(self.lam[self.k] / (mu * 0.9)))
        if self.n > P["n_min"] and not self.pending and util * self.n / (self.n - 1) < 0.5:
            self.unneeded += 1
        else:
            self.unneeded = 0
        if self.unneeded >= P["ca_unneeded_steps"]:
            self.unneeded = 0
            return total - 1
        return total

    def step(self):
        P, k, dt = self.P, self.k, self.P["dt"]
        self.n += sum(1 for s in self.pending if s <= k)
        self.pending = [s for s in self.pending if s > k]
        self.cap = cap = self.override.get("power", 1.0)
        mu = self.mu(cap)
        A = self.lam[k] * dt
        if self.override.get("admission", None) == 0.0:            # paced: the job is suspended, its work held
            self.H += A
            A = 0.0
        else:                                                      # running: held work comes back
            A += self.H
            self.H = 0.0
        limit = P["queue_limit_s"] * self.n * mu
        C = self.n * mu * dt
        adm = min(A, max(0.0, C + limit - self.Q))                 # what this period serves, plus the queue limit
        drop = A - adm
        served = min(self.Q + adm, C)
        self.Q += adm - served
        util = served / C if C > 0 else 1.0
        W = (self.Q + self.H) / max(self.n * mu, 1e-9) + 1.0 / mu
        p = self.n * (P["p_idle"] + P["p_dyn"] * cap * util) + len(self.pending) * P["p_idle"]
        self.m["work"] += served
        self.m["energy_j"] += p * dt
        self.m["steps"] += 1
        self.record(W > P["slo_s"] or drop > 1e-9)
        self.drop_share = drop / max(A, 1e-9) if A > 0 else 0.0
        self.power_w, self.util, self.W = p, util, W
        self.th = min(1.35, max(0.0, 0.86 * self.th + 0.14 * (0.34 + 0.62 * min(1.35, p / self.budget_w))))
        self.drift = abs(self.lam[k] - self.lam[k - 1]) / P["lam0"] if k else 0.0
        total = self.n + len(self.pending)
        want = self.cluster_autoscaler(util, mu) if P.get("ca") else self.hpa(util)
        if self.override.get("release"):
            want = min(want, total - 1)                            # one machine per decision
        want = int(clamp(want, P["n_min"], P["n_max"]))
        if want > total:
            self.pending += [k + P["startup_steps"]] * min(want - total, max(4, total))
        elif want < total:
            cut = total - want
            while cut and self.pending:
                self.pending.pop(); cut -= 1
            self.n = max(P["n_min"], self.n - cut)
        self.k += 1


# ---------------------------------------------------------------------------------------------------------------
class ThermalZone(Plant):
    template = "thermal_zone"

    def __init__(self, P, seed, steps):
        super().__init__(P, seed, steps)
        P, r = self.P, self.rng
        noise = ar_trace(r, steps, 0.95, P["noise"])
        ph = r.uniform(-0.5, 0.5)
        per = 86400.0 / P["dt"]
        self.qit = [P["q_it_w"] * (1.0 + P["it_amp"] * math.sin(2 * math.pi * (k / per + ph)) + noise[k])
                    for k in range(steps)]
        self.tout = [P["t_out"] + P["t_out_amp"] * math.sin(2 * math.pi * (k / per - 0.25 + P["start_frac"]))
                     + r.gauss(0, 0.3) for k in range(steps)]
        self.T = P["t_set"]
        self.integ = 0.0
        self.units_on = P["units"]
        self.qc_avg, self.qc_cmd_avg, self.drift = P["q_it_w"], P["q_it_w"], 0.0
        cop = self.cop(P["t_set"], P["t_out"])
        self.nominal_w = P["q_it_w"] / cop + 0.6 * P["units"] * P["p_unit_w"]
        self.full_w = P["units"] * P["q_unit_w"] / cop + P["units"] * P["p_unit_w"]

    def cop(self, tset, tout):
        tsup = tset - self.P["approach"]
        return clamp(self.P["eta"] * (tsup + 273.15) / max(3.0, tout + 5.0 - tsup), 2.0, 10.0)

    def setpoint(self):
        return self.override.get("setpoint", self.P["t_set"])

    def omni_override(self, knob, d, g, auth):
        P, clean, rho = self.P, self.slo_clean, rho_of(d)
        if knob == "setpoint":
            # the live cooling law: warm setpoint while cool, cold as heat rises, under the nervous-system ceiling
            th = self.zone_thermal()
            x = clamp((th - 0.5) / 0.5, 0.0, 1.0)
            c = P["calm"] - (P["calm"] - P["stress"]) * x
            c = min(c, P["stress"] + (P["calm"] - P["stress"]) * calm_of(auth))
            if c > P["t_set"] and not (organ(auth, "cooling").get("contract") and clean):
                c = P["t_set"]                                     # warming gives cooling back: needs authority
            return {"setpoint": c}
        if knob == "capacity":                                     # cooling units: the release gate
            u = self.units_on
            ok = (organ(auth, "cooling").get("contract") and clean and u > 1 and self.T <= self.setpoint()
                  and self.qc_cmd_avg / ((u - 1) * P["q_unit_w"]) <= rho)
            return {"release": 1.0} if ok else {}
        if knob == "power":
            if not may_contract(auth, "power", clean):
                return {}
            floor = min(1.0, 1.1 * self.qc_cmd_avg / max(self.units_on * P["q_unit_w"], 1e-9))
            return {"power": envelope_cap(auth, "power", d, floor)}
        return {"admission": 0.0} if self.paced else {}

    def observe(self):
        P = self.P
        base = P["t_set"] - 6.0
        th = clamp((self.T - base) / (P["t_limit"] - base), 0.0, 1.5)
        return {"queue_ratio": max(0.0, self.T - self.setpoint()) / max(P["t_limit"] - self.setpoint(), 0.5),
                "load_ratio": self.qc_avg / max(self.units_on * P["q_unit_w"] * self.override.get("power", 1.0), 1e-9),
                "power_stress": self.power_w / self.full_w, "thermal": th, "network_stress": 0.0,
                "drift_ratio": self.drift, "stale": 0.0, "security_block": 0.0}

    def zone_thermal(self):
        return self.observe()["thermal"]

    def step(self):
        P, k = self.P, self.k
        sub = P["sub"]
        dts = P["dt"] / sub
        tset = self.setpoint()
        cap = self.override.get("power", 1.0)
        shed = 0.9 if self.override.get("admission", 1.0) == 0.0 else 1.0
        q_own = max(0.0, self.qit[k]) * shed
        q_load = q_own + max(0.0, self.ext.get("heat_w", 0.0))
        qmax = self.units_on * P["q_unit_w"] * cap
        cop = self.cop(tset, self.tout[k])
        e = qc_sum = cmd_sum = 0.0
        hot = False
        for _ in range(sub):
            err = self.T - tset
            cmd = q_load + P["kp"] * err + P["ki"] * self.integ
            qc = clamp(cmd, 0.0, qmax)
            if 0.0 < cmd < qmax or (cmd >= qmax and err < 0) or (cmd <= 0 and err > 0):
                self.integ += err * dts
            self.T += (q_load + P["ua"] * (self.tout[k] - self.T) - qc) * dts / P["c_j_k"]
            p = qc / cop + self.units_on * P["p_unit_w"]
            e += p * dts
            qc_sum += qc
            cmd_sum += max(cmd, 0.0)
            if self.T > P["t_limit"]:
                hot = True
            else:
                self.m["work"] += q_own * dts
        self.m["energy_j"] += e
        self.m["steps"] += 1
        self.record(hot)
        self.power_w = e / P["dt"]
        self.qc_avg, self.qc_cmd_avg = qc_sum / sub, cmd_sum / sub
        self.drift = abs(self.qit[k] - self.qit[k - 1]) / P["q_it_w"] if k else 0.0
        staged = int(clamp(math.ceil(self.qc_cmd_avg / (0.8 * P["q_unit_w"]) - 1e-9), 1, P["units"]))
        if self.override.get("release"):
            staged = min(staged, self.units_on - 1)                # one unit per decision
        self.units_on = int(clamp(staged, 1, P["units"]))
        self.k += 1


# ---------------------------------------------------------------------------------------------------------------
class EnergyStorage(Plant):
    template = "energy_storage"

    def __init__(self, P, seed, steps):
        super().__init__(P, seed, steps)
        P, r = self.P, self.rng
        noise = ar_trace(r, steps, 0.9, P["noise"])
        cloud = ar_trace(r, steps, 0.97, 0.08)
        self.load, self.pv = [], []
        for k in range(steps):
            h = (P["start_h"] + k * P["dt"] / 3600.0) % 24.0
            shape = 1.0 + P["load_amp"] * math.cos(2 * math.pi * (h - P["peak_h"]) / 24.0)
            self.load.append(max(0.0, P["load_w"] * shape * (1.0 + noise[k])))
            sun = max(0.0, math.sin(math.pi * (h - 6.0) / 12.0)) if 6.0 <= h <= 18.0 else 0.0
            self.pv.append(P["pv_w"] * sun * clamp(0.85 + cloud[k], 0.2, 1.0))
        self.soc = self.soc0 = P["soc0"]
        self.deferred_j = 0.0
        self.imp, self.net, self.drift = 0.0, 0.0, 0.0
        self.E = P["e_wh"] * 3600.0
        self.nominal_w = max(P["load_w"] - 0.32 * P["pv_w"], 0.2 * P["load_w"])

    def omni_override(self, knob, d, g, auth):
        P, clean = self.P, self.slo_clean
        if knob == "setpoint":
            # reserve by power stress: released as the connection nears its limit (more protection: always allowed);
            # held above native while calm only with contraction authority (it withholds battery energy)
            x = clamp((self.imp / P["p_lim_w"] - 0.5) / 0.5, 0.0, 1.0)
            r = P["calm"] - (P["calm"] - P["stress"]) * x
            if r > P["reserve"] and not may_contract(auth, "power", clean):
                r = P["reserve"]
            return {"setpoint": r}
        if knob == "capacity":                                     # the ceiling the battery defends: rho* (expand only)
            return {"capacity": rho_of(d)}
        if knob == "power":
            if not may_contract(auth, "power", clean):
                return {}
            return {"power": envelope_cap(auth, "power", d, 0.0)}
        return {"admission": 0.0} if self.paced else {}

    def observe(self):
        P = self.P
        return {"queue_ratio": self.deferred_j / (P["p_lim_w"] * P["dt"] * 10.0),
                "load_ratio": max(0.0, self.net) / P["p_lim_w"], "power_stress": self.imp / P["p_lim_w"],
                "thermal": self.thermal_obs(0.3), "network_stress": 0.0, "drift_ratio": self.drift,
                "stale": 0.0, "security_block": 0.0}

    def step(self):
        P, k, dt = self.P, self.k, self.P["dt"]
        ext = self.ext.get("load_w", 0.0)
        L_own = self.load[k]
        L = max(0.0, L_own + ext)
        pv = self.pv[k]
        if self.override.get("admission", None) == 0.0:            # paced: defer the flexible share
            defer = P["flex"] * L_own
            self.deferred_j += defer * dt
            L -= defer
            served_own = L_own - defer
        else:                                                      # catch up while the connection has room
            room = max(0.0, 0.8 * P["p_lim_w"] - (L - pv))
            s = min(self.deferred_j / dt, room)
            self.deferred_j -= s * dt
            L += s
            served_own = L_own + s
        net = L - pv
        reserve = self.override.get("setpoint", P["reserve"])
        pmax = P["p_batt_w"] * self.override.get("power", 1.0)
        sq = math.sqrt(P["eta_rt"])
        if net < 0.0:
            ch = min(-net, pmax, (1.0 - self.soc) * self.E / (dt * sq))
            self.soc += ch * dt * sq / self.E
            imp = 0.0
        else:
            d = min(net, pmax, max(0.0, self.soc - reserve) * self.E * sq / dt)
            if "capacity" in self.override:
                thr = self.override["capacity"] * P["p_lim_w"]
                d += max(0.0, min(net - d - thr, pmax - d, self.soc * self.E * sq / dt - d))
            self.soc -= d * dt / (self.E * sq)
            imp = net - d
        self.m["work"] += served_own * dt
        self.m["energy_j"] += (imp - ext) * dt                     # the external load is metered where it is drawn
        self.m["steps"] += 1
        self.record(imp > P["p_lim_w"])
        self.drift = abs(pv - self.pv[k - 1]) / max(P["pv_w"], 1.0) if k else 0.0
        self.imp, self.net, self.power_w = imp, net, imp - ext
        self.k += 1

    def finalize(self):
        # battery energy left below (or above) where it started is bought back (or credited) at the round trip
        self.m["energy_j"] += (self.soc0 - self.soc) * self.E / math.sqrt(self.P["eta_rt"])


# ---------------------------------------------------------------------------------------------------------------
class MotionAxis(Plant):
    template = "motion_axis"

    def __init__(self, P, seed, steps):
        super().__init__(P, seed, steps)
        P, r = self.P, self.rng
        self.arrivals, self.tau_d = [], []
        rate_noise = ar_trace(r, steps, 0.95, 0.15)
        td = 0.0
        for k in range(steps):
            lam = P["task_rate"] * math.exp(rate_noise[k]) * P["dt_dec"]
            # Poisson count by inversion
            n, p, u = 0, math.exp(-lam), r.random()
            c = p
            while u > c and n < 50:
                n += 1; p *= lam / n; c += p
            self.arrivals.append(n)
            if r.random() < 0.1:
                td = r.uniform(-P["dist"], P["dist"])
            self.tau_d.append(P["load_bias"] + td)
        self.theta = self.omega = self.integ = 0.0
        self.Tm = P["t_amb"]
        self.backlog, self.waits = 0, []
        self.move = None
        self.dwell = 0.0
        self.pos = 0.0
        self.s = 1.0
        self.demand_rate = P["task_rate"]
        self.err_max = self.drift = 0.0
        self.tau_peak = 0.0
        self.rated_w = P["p_idle"] + P["R"] * (P["tau_max"] / P["kt"]) ** 2 * 0.3
        self.nominal_w = self.rated_w

    def move_time(self, s):
        v, a, D = self.P["v_max"] * s, self.P["a_max"] * s, self.P["D"]
        return 2.0 * math.sqrt(D / a) if D < v * v / a else D / v + v / a

    def omni_override(self, knob, d, g, auth):
        P, clean = self.P, self.slo_clean
        if knob == "admission":
            return {"admission": 0.0} if self.paced else {}
        if not clean:
            return {}                                              # SLO reflex: full speed and effort at once
        if knob == "power":
            if not may_contract(auth, "gpu", clean):
                return {}
            return {"power": envelope_cap(auth, "gpu", d, min(1.0, 1.3 * self.tau_peak / P["tau_max"]))}
        load = self.demand_rate * (self.move_time(self.s) + P["dwell"])
        return {"capacity": continuous_capacity(self.s, load, rho_of(d), auth, "pods", clean, 0.4)}

    def observe(self):
        P = self.P
        return {"queue_ratio": self.backlog / max(P["task_rate"] * 30.0, 1.0),
                "load_ratio": self.demand_rate * (self.move_time(self.s) + P["dwell"]),
                "power_stress": self.power_w / self.rated_w,
                "thermal": self.thermal_obs(clamp((self.Tm - P["t_amb"]) / (P["t_lim"] - P["t_amb"]), 0.0, 1.5)),
                "network_stress": 0.0, "drift_ratio": self.drift, "stale": 0.0, "security_block": 0.0}

    def ref(self, t):
        """Trapezoid (or triangle) reference from the move's start: position offset, velocity, acceleration."""
        mv = self.move
        v, a, D, T = mv["v"], mv["a"], self.P["D"], mv["T"]
        ta = v / a if D >= v * v / a else math.sqrt(D / a)
        vp = a * ta
        if t < ta:
            return 0.5 * a * t * t, a * t, a
        if t < T - ta:
            return 0.5 * a * ta * ta + vp * (t - ta), vp, 0.0
        if t < T:
            tr = T - t
            return D - 0.5 * a * tr * tr, a * tr, -a
        return D, 0.0, 0.0

    def step(self):
        P, k = self.P, self.k
        dt = P["dt"]
        n = int(round(P["dt_dec"] / dt))
        self.backlog += self.arrivals[k]
        self.waits += [0.0] * self.arrivals[k]
        self.demand_rate = 0.9 * self.demand_rate + 0.1 * self.arrivals[k] / P["dt_dec"]
        self.s = self.override.get("capacity", 1.0)
        effort = self.override.get("power", 1.0)
        admit = self.override.get("admission", 1.0) >= 0.5
        e = 0.0
        err_max = 0.0
        tau_peak = 0.0
        hot = False
        done = 0
        for _ in range(n):
            if self.move is None:
                if self.dwell > 0.0:
                    self.dwell -= dt
                elif self.backlog > 0 and admit:
                    sgn = 1.0 if self.pos == 0.0 else -1.0
                    self.move = {"t": 0.0, "v": P["v_max"] * self.s, "a": P["a_max"] * self.s,
                                 "T": self.move_time(self.s), "start": self.theta_ref_end(), "sgn": sgn}
            if self.move is not None:
                off, vr, ar = self.ref(self.move["t"])
                th_r = self.move["start"] + self.move["sgn"] * off
                w_r, a_r = self.move["sgn"] * vr, self.move["sgn"] * ar
                self.move["t"] += dt
            else:
                th_r, w_r, a_r = self.pos, 0.0, 0.0
            err = th_r - self.theta
            self.integ = clamp(self.integ + err * dt, -P["i_max"], P["i_max"])
            tau = P["kp"] * err + P["kd"] * (w_r - self.omega) + P["ki"] * self.integ + P["J"] * a_r + P["load_bias"]
            lim = P["tau_max"] * effort
            if self.Tm > P["t_lim"]:
                lim *= 0.5                                         # firmware derating while the winding is hot
                hot = True
            tau = clamp(tau, -lim, lim)
            tau_peak = max(tau_peak, abs(tau))
            acc = (tau - P["b"] * self.omega - self.tau_d[k]) / P["J"]
            self.omega += acc * dt
            self.theta += self.omega * dt
            i2r = P["R"] * (tau / P["kt"]) ** 2
            mech = tau * self.omega
            p = P["p_idle"] + i2r + (mech if mech > 0 else P["regen"] * mech)
            e += p * dt
            self.Tm += (i2r - (self.Tm - P["t_amb"]) / P["r_th"]) * dt / P["c_th"]
            if self.move is not None:
                err_max = max(err_max, abs(err))
                if self.move["t"] >= self.move["T"] and abs(err) < P["tol"] and abs(self.omega) < 10 * P["tol"]:
                    self.pos = self.move["start"] + self.move["sgn"] * P["D"]
                    self.move = None
                    self.dwell = P["dwell"]
                    self.backlog -= 1
                    self.waits.pop(0)
                    done += 1
        self.waits = [w + P["dt_dec"] for w in self.waits]
        late = bool(self.waits) and self.waits[0] > P["deadline_s"]
        self.m["work"] += done
        self.m["energy_j"] += e
        self.m["steps"] += 1
        self.record(err_max > P["e_max"] or hot or late)
        self.tau_peak = tau_peak
        self.power_w = e / P["dt_dec"]
        self.drift = abs(self.tau_d[k] - self.tau_d[k - 1]) / P["tau_max"] if k else 0.0
        self.k += 1

    def theta_ref_end(self):
        return self.pos


# ---------------------------------------------------------------------------------------------------------------
class ProcessLoop(Plant):
    template = "process_loop"

    def __init__(self, P, seed, steps):
        super().__init__(P, seed, steps)
        P, r = self.P, self.rng
        noise = ar_trace(r, steps, 0.9, P["noise"])
        per = 86400.0 / P["dt"]
        ph = r.uniform(0.0, 1.0)
        self.d = [max(0.0, P["d_mean"] * (1.0 + P["d_amp"] * math.sin(2 * math.pi * (k / per + ph))) + noise[k])
                  for k in range(steps)]
        self.y = P["sp"]
        self.integ = (P["sp"] + P["d_mean"]) / P["K"] / P["ki"] if P["ki"] else 0.0
        nd = max(1, int(round(P["theta"] / (P["dt"] / P["sub"]))))
        self.delay = [(P["sp"] + P["d_mean"]) / P["K"]] * nd
        self.s = 1.0
        self.umax_eff = P["u_max"]
        self.u_avg, self.dev, self.drift = (P["sp"] + P["d_mean"]) / P["K"], 0.0, 0.0
        self.nominal_w = P["p_max_w"] * (((P["sp"] + P["d_mean"]) / P["K"]) / P["u_max"]) ** P["aff"]

    def setpoint(self):
        return self.override.get("setpoint", self.P["sp"])

    def omni_override(self, knob, d, g, auth):
        P, clean = self.P, self.slo_clean
        if knob == "admission":
            return {"admission": 0.0} if self.paced else {}
        if not clean:
            return {}                                              # SLO reflex: native at once
        if knob == "setpoint":
            if not may_contract(auth, "power", clean):
                return {}
            sp = self.setpoint()
            return {"setpoint": sp + calm_of(auth) * (P["calm"] - sp)}
        if knob == "power":
            if not may_contract(auth, "power", clean):
                return {}
            return {"power": envelope_cap(auth, "power", d, min(1.0, 1.1 * (self.u_avg / P["u_max"]) ** P["aff"]))}
        return {"capacity": continuous_capacity(self.s, self.u_avg / self.umax_eff, rho_of(d), auth, "pods", clean,
                                                0.3)}

    def observe(self):
        P = self.P
        return {"queue_ratio": self.dev, "load_ratio": self.u_avg / self.umax_eff,
                "power_stress": self.power_w / P["p_max_w"], "thermal": self.thermal_obs(0.3),
                "network_stress": 0.0, "drift_ratio": self.drift, "stale": 0.0, "security_block": 0.0}

    def step(self):
        P, k = self.P, self.k
        sub = P["sub"]
        dts = P["dt"] / sub
        sp = self.setpoint()
        self.s = self.override.get("capacity", 1.0)
        umax = self.umax_eff = P["u_max"] * self.s * self.override.get("power", 1.0) ** (1.0 / P["aff"])
        frac = 0.9 if self.override.get("admission", 1.0) < 0.5 else 1.0
        dk = self.d[k] * frac
        e = u_sum = dev = 0.0
        out = False
        for _ in range(sub):
            err = sp - self.y
            u_raw = P["kp"] * err + P["ki"] * self.integ
            u = clamp(u_raw, 0.0, umax)
            if 0.0 < u_raw < umax or (u_raw >= umax and err < 0) or (u_raw <= 0 and err > 0):
                self.integ += err * dts
            self.delay.append(u)
            ud = self.delay.pop(0)
            self.y += (-self.y + P["K"] * ud - dk) * dts / P["tau"]
            e += P["p_max_w"] * (u / P["u_max"]) ** P["aff"] * dts
            u_sum += u
            dv = abs(self.y - P["mid"]) / P["half"]
            dev = max(dev, abs(self.y - sp) / P["half"])
            if dv > 1.0:
                out = True
            else:
                self.m["work"] += dk * dts
        self.m["energy_j"] += e
        self.m["steps"] += 1
        self.record(out)
        self.power_w = e / P["dt"]
        self.u_avg, self.dev = u_sum / sub, dev
        self.drift = abs(self.d[k] - self.d[k - 1]) / max(P["d_mean"], 1e-9) if k else 0.0
        self.k += 1


TEMPLATES = {c.template: c for c in (ComputePool, ThermalZone, EnergyStorage, MotionAxis, ProcessLoop)}
