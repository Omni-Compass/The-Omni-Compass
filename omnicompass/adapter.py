"""Omni-Compass stack governor.

  sense      : stack telemetry -> normalized observation vector
  assimilate : observation blended into the six-state engine state
  evolve     : one macro step of equations (1)-(7) with u = 0
  allocate   : engine state -> directive (capacity, change gating, power, rollback, routing, alerting, paging)
  authority  : OBSERVE | AUTOPILOT; kill() revokes authority and returns control to the native managers
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

from .core import State, Params, macro_step, v_eff, control_command, U_AUTHORITY

OBSERVE = "observe"
AUTOPILOT = "autopilot"

# Engine parameters used for stack governance (fixed, not sampled).
STACK_PARAMS = Params(alpha=4.2, beta_int=0.0, beta_ext=0.0, k=1.7, sigma_1=0.38, delta=0.705, gamma_1=1.35,
                      gamma_c=1.0, lambda_0=-0.40, lambda_1=1.55, lambda_2=1.15, c=1.0, E_max=2.0,
                      omega_B=1.0, Q_B=2.5, alpha_s=0.12, beta_s=0.10, mu=3.782, alpha_E=3.487, alpha_U=4.2,
                      lambda_I=0.719, lambda_U=0.0)
INITIAL_STATE = State(E=0.12, U=0.82, I_U=0.0, S=0.0, B=0.0, B_dot=0.0)
ASSIMILATION = 0.339


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def observe_vector(obs: Dict[str, float], conflicts: int) -> Dict[str, float]:
    """Normalize telemetry. Inputs are the stack's delayed observations."""
    return {
        "q": clamp(float(obs.get("queue_ratio", 0.0)), 0.0, 2.0),
        "load": clamp(float(obs.get("load_ratio", 0.0)), 0.0, 2.0),
        "power": clamp(float(obs.get("power_stress", 0.0)), 0.0, 1.5),
        "thermal": clamp(float(obs.get("thermal", 0.0)), 0.0, 1.5),
        "network": clamp(float(obs.get("network_stress", 0.0)), 0.0, 1.5),
        "drift": clamp(float(obs.get("drift_ratio", 0.0)), 0.0, 1.5),
        "stale": clamp(float(obs.get("stale", 0.0)), 0.0, 1.0),
        "security": clamp(float(obs.get("security_block", 0.0)), 0.0, 1.0),
        "conflict": clamp(conflicts / 4.0, 0.0, 1.0),
    }


def assimilate(x: State, o: Dict[str, float], p: Params) -> State:
    """Blend the observation into the engine state and set the forcing terms."""
    q, load, pw, th, nw, dr, st, sec, cf = (o[k] for k in
        ("q", "load", "power", "thermal", "network", "drift", "stale", "security", "conflict"))
    e_obs = clamp(0.25 * q + 0.18 * max(0.0, load - 0.85) + 0.16 * pw + 0.13 * th + 0.10 * nw + 0.08 * dr
                  + 0.06 * cf + 0.04 * st, 0.0, 1.5)
    u_obs = clamp(1.0 - (0.27 * q + 0.18 * pw + 0.16 * th + 0.12 * nw + 0.12 * dr + 0.10 * cf + 0.05 * st), 0.0, 1.0)
    s_obs = clamp(0.36 * th + 0.28 * pw + 0.18 * nw + 0.10 * sec + 0.08 * st - 0.20 * q, -1.0, 1.0)
    b_obs = clamp(0.52 * pw + 0.26 * th + 0.22 * dr, -1.0, 1.5)
    i_obs = clamp(q + dr + cf, 0.0, 2.0)
    a = ASSIMILATION
    p.beta_int = clamp(0.58 * q + 0.42 * max(0.0, load - 0.75), 0.0, 1.0)
    p.beta_ext = clamp(0.33 * pw + 0.27 * th + 0.20 * nw + 0.12 * st + 0.08 * sec, 0.0, 1.0)
    return State(E=(1 - a) * x.E + a * e_obs, U=(1 - a) * x.U + a * u_obs, I_U=(1 - a) * x.I_U + a * i_obs,
                 S=(1 - a) * x.S + a * s_obs, B=(1 - a) * x.B + a * b_obs, B_dot=(1 - a) * x.B_dot + a * (b_obs - x.B))


@dataclass(frozen=True)
class AllocationLaw:
    """Engine state -> governing directive.

    release    capacity removed only while push <= push_release (the engine's controller reports convergence)
    add        without backlog, capacity added only while push >= push_add (the engine's controller reports need)
    push       equation (2) control law evaluated on the evolved state with target sigma = +1:
               u = clip(-f_U(x) + KP (1 - U), -U_AUTHORITY, U_AUTHORITY);  push = u / U_AUTHORITY
               (f_U contains the double-well drift and -(dE/dt)/E_max from equation (1))
    headroom   rho* = clamp(rho0 - kI*I_U - kE*E, rho_min, rho0)
    sizing     load_s = load * cap_now if size_at_full_cap else load
    capacity   n_req = ceil(n * load / rho*) + ceil(kq * q * n);  delta = clamp(n_req - n, -down_max, +up_max)
    guard      no capacity removal while q >= guard_queue
    band       capacity removed only when n_req <= n - down_band
    dwell      capacity removed only after surplus persists for down_dwell intervals and no earlier than
               down_after_add intervals after the last addition
    envelope   no capacity addition while observed power >= power_ceiling (power_ceiling_backlog while q >= guard_queue)
    security   no capacity addition while a security block is observed
    change     Terraform plans only while U >= U_gate, only in the direction of the live capacity decision
    power      q < guard_queue and U >= U_gate: cap = clamp(cap_now * load * (1 + margin), cap_min, 1)   (trim to demand)
               q >= guard_queue at the power envelope: cap = max(cap_min, cap_now - spread_step)      (spread)
               q >= guard_queue below the envelope: cap held (capacity added as nodes; 1 at max_nodes)
               otherwise cap = 1; always cap <= 1 - cap_gain * max(0, B - B_cap)
    rollback   a proposed rollback is authorised if S >= S_rollback, U is falling, or security blocks change
    replicas   direct actuation: desired = ceil(replicas * load / rho*) (the HPA formula with the engine-set target),
               increases unless capacity is being reduced, decreases only while reducing;
               otherwise autoscaler increases approved unless reducing, decreases only while reducing
    consistency a step that expands capacity never tightens the power cap
    paging     none: the governor holds every action a paged operator would take
    """
    rho0: float = 0.914
    rho_min: float = 0.627
    kI: float = 0.252
    kE: float = 0.297
    kq: float = 0.795
    up_max: int = 2
    down_max: int = 1
    guard_queue: float = 0.05
    power_ceiling: float = 0.95
    power_ceiling_backlog: float = 1.00
    spread_step: float = 0.05
    backlog_release: bool = False
    size_at_full_cap: bool = False
    push_release: float = 0.005
    push_add: float = -9.0
    U_gate: float = 0.481
    margin: float = 0.006
    cap_min: float = 0.706
    B_cap: float = 0.40
    cap_gain: float = 0.60
    S_rollback: float = 0.55
    route_network: float = 0.20
    down_band: int = 4
    down_dwell: int = 4
    down_after_add: int = 4
    min_nodes: int = 8
    max_nodes: int = 40


@dataclass
class Governor:
    law: AllocationLaw = field(default_factory=AllocationLaw)
    mode: str = AUTOPILOT
    killed: bool = False
    x: State = field(default_factory=lambda: State(**asdict(INITIAL_STATE)))
    p: Params = field(default_factory=lambda: Params(**asdict(STACK_PARAMS)))
    t: float = 0.0
    current_cap: float = 1.0
    nodes: int = 20
    surplus_streak: int = 0
    since_add: int = 99
    last_push: float = 0.0
    log: deque = field(default_factory=lambda: deque(maxlen=4096))
    evolve: bool = True

    def kill(self) -> None:
        """Revoke authority; the engine continues to compute and log directives."""
        self.killed = True

    def set_mode(self, mode: str) -> None:
        if mode not in (OBSERVE, AUTOPILOT):
            raise ValueError(mode)
        self.mode = mode

    @property
    def has_authority(self) -> bool:
        return self.mode == AUTOPILOT and not self.killed

    def step(self, obs: Dict[str, float], conflicts: int) -> Dict[str, Any]:
        """Sense, assimilate, evolve, allocate."""
        o = observe_vector(obs, conflicts)
        U_before = self.x.U
        xa = assimilate(self.x, o, self.p)
        if self.evolve:
            xn, _ = macro_step(xa, self.p, self.t, target=None)
        else:
            xn = xa
        self.x = xn
        self.t += 0.1
        L = self.law
        n = int(self.nodes)
        u_push, _ = control_command(xn, self.p, self.t, +1)
        push = u_push / U_AUTHORITY
        self.last_push = push
        rho = clamp(L.rho0 - L.kI * xn.I_U - L.kE * xn.E, L.rho_min, L.rho0)
        converged = push <= L.push_release
        load_sized = o["load"] * self.current_cap if L.size_at_full_cap else o["load"]
        n_req = math.ceil(n * load_sized / rho) + math.ceil(L.kq * o["q"] * n)
        delta = max(-L.down_max, min(L.up_max, n_req - n))
        if delta < 0 and not converged:
            delta = 0
        if delta > 0 and o["q"] < L.guard_queue and push < L.push_add:
            delta = 0
        if delta < 0 and (o["q"] >= L.guard_queue or n_req > n - L.down_band):
            delta = 0
        self.surplus_streak = self.surplus_streak + 1 if delta < 0 else 0
        if delta < 0 and (self.surplus_streak < L.down_dwell or self.since_add < L.down_after_add):
            delta = 0
        ceiling = L.power_ceiling_backlog if o["q"] >= L.guard_queue else L.power_ceiling
        if delta > 0 and (o["power"] >= ceiling or n >= L.max_nodes):
            delta = 0
        if o["security"] > 0.5:
            delta = min(delta, 0)
        self.since_add = 0 if delta > 0 else self.since_add + 1
        if delta < 0:
            self.surplus_streak = 0
        at_envelope = o["power"] >= ceiling
        if o["q"] < L.guard_queue and xn.U >= L.U_gate:
            cap = clamp(self.current_cap * o["load"] * (1.0 + L.margin), L.cap_min, 1.0)
        elif o["q"] >= L.guard_queue and L.spread_step > 0.0:
            if at_envelope:
                cap = clamp(self.current_cap - L.spread_step, L.cap_min, 1.0)
            else:
                cap = 1.0 if L.backlog_release else (self.current_cap if n < L.max_nodes else 1.0)
        elif o["q"] >= L.guard_queue and L.backlog_release:
            cap = 1.0
        else:
            cap = 1.0
        cap = min(cap, clamp(1.0 - L.cap_gain * max(0.0, xn.B - L.B_cap), L.cap_min, 1.0))
        if delta > 0:
            cap = max(cap, self.current_cap)
        command = clamp(0.5 * (v_eff(xn, self.p) / max(self.p.c, 1e-9) + 1.0), 0.0, 1.0)
        d = {
            "node_delta": int(delta),
            "change_permitted": xn.U >= L.U_gate and o["security"] <= 0.5,
            "power_cap": cap,
            "rollback_authorized": xn.S >= L.S_rollback or xn.U < U_before or o["security"] > 0.5,
            "route_shift": o["network"] > L.route_network,
            "state": {"E": xn.E, "U": xn.U, "I_U": xn.I_U, "S": xn.S, "B": xn.B},
            "demand": rho,
            "load": o["load"],
            "command": command,
        }
        self.log.append({"mode": self.mode, "killed": self.killed, **{k: v for k, v in d.items() if k != "state"},
                         **d["state"]})
        return d


def directive_to_actions(d: Dict[str, Any], stack_state: Dict[str, Any], proposals: List[Dict[str, Any]],
                         cfg, direct_actuation: bool = False) -> List[Dict[str, Any]]:
    """Directive -> executable stack actions. direct_actuation: capacity is owned by the governor; no Terraform plans."""
    tag = "Omni-Compass"
    out: List[Dict[str, Any]] = []
    cur = int(stack_state["actual_nodes"])
    target = int(max(cfg.minimum_nodes, min(cfg.maximum_nodes, cur + int(d["node_delta"]))))
    if target != cur:
        out.append({"manager": tag, "action": "nodes", "target": target, "direction": 1 if target > cur else -1})
    if not direct_actuation and d["change_permitted"] and any(p["action"] == "terraform_plan" for p in proposals):
        tf_dir = 1 if target > stack_state["terraform_desired_nodes"] else -1
        live_dir = 1 if target > cur else -1 if target < cur else 0
        if abs(target - stack_state["terraform_desired_nodes"]) >= 2 and live_dir in (0, tf_dir):
            out.append({"manager": tag, "action": "terraform_plan", "target": target,
                        "direction": 1 if target > stack_state["terraform_desired_nodes"] else -1})
    reps = [int(p["target"]) for p in proposals if p["action"] == "replicas"]
    if direct_actuation:
        cur_r = int(stack_state["replicas"])
        rt = max(20, min(500, math.ceil(cur_r * float(d["load"]) / max(float(d["demand"]), 1e-9))))
        if (rt > cur_r and d["node_delta"] >= 0) or (rt < cur_r and d["node_delta"] < 0):
            out.append({"manager": tag, "action": "replicas", "target": rt, "direction": 1 if rt > cur_r else -1})
        reps = []
    if reps:
        cur_r = int(stack_state["replicas"])
        rt = None
        if d["node_delta"] >= 0 and max(reps) > cur_r:
            rt = max(reps)
        elif d["node_delta"] < 0 and min(reps) < cur_r:
            rt = min(reps)
        if rt is not None:
            out.append({"manager": tag, "action": "replicas", "target": rt,
                        "direction": 1 if rt > cur_r else -1})
    cap = float(d["power_cap"])
    if any(a["direction"] > 0 and a["action"] in ("nodes", "terraform_plan", "replicas") for a in out):
        cap = max(cap, float(stack_state["power_cap"]))
    if abs(cap - stack_state["power_cap"]) > 1e-9:
        out.append({"manager": tag, "action": "power_cap", "target": cap,
                    "direction": -1 if cap < stack_state["power_cap"] else 1})
    if d["route_shift"]:
        out.append({"manager": tag, "action": "route_shift", "target": 1.0, "direction": 1})
    if any(p["action"] == "rollback" for p in proposals) and d["rollback_authorized"]:
        out.append({"manager": tag, "action": "rollback", "target": 1.0, "direction": -1})
    alerts = [p for p in proposals if p["action"] == "alert"]
    if alerts:
        out.append({"manager": tag, "action": "alert", "target": max(int(p["target"]) for p in alerts), "direction": 1})
    return out


THROUGHPUT_MODE = dict(backlog_release=True, power_ceiling=9.0, power_ceiling_backlog=9.0, spread_step=0.0, B_cap=9.0,
                       size_at_full_cap=True, kI=0.05, kE=0.40, cap_min=0.65, down_band=1, down_dwell=10,
                       down_after_add=3, kq=0.30, U_gate=0.45, push_release=0.01)


FLEET_MODE = dict(THROUGHPUT_MODE, rho0=0.829, rho_min=0.769, kI=0.072, kE=0.487, kq=0.635, down_band=3, down_dwell=1, down_after_add=5, push_release=0.053, cap_min=0.695, margin=0.131, U_gate=0.85, up_max=8)
FLEET_BALANCED_MODE = dict(FLEET_MODE, push_release=0.0098, push_add=0.0098)
FLEET_WEAR_MODE = dict(FLEET_MODE, push_release=0.0035, push_add=0.0035)
FLEET_DECISION_SECONDS = 60


def mode_law(mode: str, base: "AllocationLaw" = None) -> "AllocationLaw":
    """Operating modes.

    power_protect  the site power limit is enforced (envelope, spread-and-throttle, bath cap; shield I4 active)
    fleet          throughput mode with constants selected on the 15-second fleet harness (fleet/), decisions every 60 s;
                   energy-first: the equation (2) release gate is lenient and the add gate is off
    fleet_balanced fleet with the equation (2) gate active in both directions at 0.0098 (release and add)
    fleet_wear     fleet with the equation (2) gate active in both directions at 0.0035 (release and add)
    throughput     the power envelope is not enforced (same power rules as the native stack); caps released on backlog;
                   capacity sized at full power (load * cap_now), so power trimming does not trigger machine starts;
                   constants selected by constrained search on development seeds (minimum energy subject to backlog,
                   health, recovery, reversal and invariant constraints)
    """
    from dataclasses import replace
    base = base or AllocationLaw()
    if mode == "power_protect":
        return base
    if mode == "throughput":
        return replace(base, **THROUGHPUT_MODE)
    if mode == "fleet":
        return replace(base, **FLEET_MODE)
    if mode == "fleet_balanced":
        return replace(base, **FLEET_BALANCED_MODE)
    if mode == "fleet_wear":
        return replace(base, **FLEET_WEAR_MODE)
    raise ValueError(mode)

