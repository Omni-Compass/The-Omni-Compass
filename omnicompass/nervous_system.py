"""The supervisory nervous system: one evolving engine state grants authority to every organ family.

Omni-Compass does not replace the specialist controllers. Each keeps its own mechanism:
- the HPA and VPA size pods;
- the Cluster Autoscaler and Karpenter size node pools;
- Linux schedutil picks CPU frequency;
- NVIDIA DCGM manages GPUs;
- rollout controllers and routers do their own work.

The nervous system decides, from one shared state, the envelope inside which each of them may act.

Inputs, all from the six-state engine (omnicompass/core.py, via the governor), and nothing tuned per organ:
  kappa  convergence   = 1 if push <= push_release, else push_release / push. This is the equation-(2) gate made
                         continuous: the further the engine is from its basin, the less it may give back.
  h      basin health  = clamp((U - U_gate) / (1 - U_gate), 0, 1)
  sigma  stress ratio  = S / S*, where S* solves delta - alpha_s S - (3/4) beta_s S^2 = 0 (equation 6)
  nu     unmet need    = max(0, I_U) (equation 3)
  calm                 = kappa * h * (1 - clamp(sigma - 1, 0, 1)) * (1 - clamp(nu, 0, 1))
                         in [0, 1]; 1 means fully settled

Authority per organ:
  expand     may the organ add capacity or performance. Always yes, except during a security hold.
  contract   may it give capacity or performance back. Only when calm >= the organ's reversibility threshold
             (theta_pods 0.5, theta_nodes 0.7: a node costs a boot to reverse) and the SLO is clean.
  step       fraction of the organ's surplus it may shed this decision. Equals calm.
  envelope   for continuous organs, the allowed range:
               cpufreq ceiling (fraction of cpuinfo_max) in [1 - 0.35 calm, 1];
               GPU power limit (fraction of max) in [1 - 0.30 calm, 1];
               site power cap in [0.65, 1];
               traffic-shift fraction in [0, 0.5 calm];
               cooling supply-air setpoint (C) in [18, 18 + 9 calm].
             Heat above 0.96 forces the frequency and GPU ceilings down to 1 - 0.35 x excess.
  batch      admit held work only if calm >= 0.5 and power stress < 0.9; pause pausable work if sigma > 1, power
             stress >= 0.95, or heat >= 0.96.
  rollback   the engine's rollback authorisation (S high, U falling, or a security hold).

Global rules, applied last:
  - observe: every authority is computed and logged; execute is False everywhere.
  - kill: no authority at all.
  - security hold: no capacity organ may expand. Cooling is the one protective organ: "expand" there means more
    cooling, which adds protection and no capacity, so it stays allowed.
The safety shield (omnicompass/shield.py) stays downstream and can still veto any action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from omnicompass.closure import stress_equilibrium

ORGANS = ("pods", "nodes", "cpufreq", "gpu", "power", "batch", "routing", "rollback")
# The living band (the founder's rule): every level the nervous system hands out lives between 5% and 95% of its range.
# Nothing is driven to zero (a part with no work idles down to its floor, alive and ready) and nothing is driven to its
# absolute top (the last 5% is never spent). The band is applied last, to every envelope, so no organ can leave it.
BAND = (0.05, 0.95)


def in_band(lo: float, hi: float) -> list:
    """Clip an envelope [lo, hi] (fractions of the organ's range) into the living band, keeping lo <= hi."""
    b0, b1 = BAND
    h = min(b1, max(b0, hi))
    return [min(h, max(b0, lo)), h]


THETA = {"pods": 0.5, "nodes": 0.7, "cpufreq": 0.3, "gpu": 0.3, "power": 0.3, "routing": 0.5}


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


@dataclass(frozen=True)
class NervousInputs:
    E: float; U: float; I_U: float; S: float
    push: float
    push_release: float = 0.2
    U_gate: float = 0.5
    s_eq: float = 1.0
    security_block: float = 0.0
    slo_clean: bool = True
    power_stress: float = 0.0
    thermal: float = 0.0
    rollback: bool = False
    stale: float = 0.0               # fraction of declared senses that are blind (dropout, frozen, unreadable)
    mode: str = "autopilot"          # "observe" or "autopilot"
    killed: bool = False


def scalars(i: NervousInputs) -> Dict[str, float]:
    kappa = 1.0 if i.push <= i.push_release else i.push_release / max(i.push, 1e-12)
    h = clamp((i.U - i.U_gate) / max(1.0 - i.U_gate, 1e-12), 0.0, 1.0)
    sigma = i.S / i.s_eq if i.s_eq > 0 else 0.0
    nu = max(0.0, i.I_U)
    calm = kappa * h * (1.0 - clamp(sigma - 1.0, 0.0, 1.0)) * (1.0 - clamp(nu, 0.0, 1.0))
    return {"kappa": kappa, "h": h, "sigma": sigma, "nu": nu, "calm": clamp(calm, 0.0, 1.0)}


def authority(i: NervousInputs) -> Dict[str, Any]:
    if i.killed:
        return {"execute": False, "killed": True, "organs": {}}
    sc = scalars(i); calm = sc["calm"]
    sec = i.security_block > 0.5
    hot = i.thermal >= 0.96
    excess = clamp(i.thermal - 0.96, 0.0, 1.0)
    org: Dict[str, Dict[str, Any]] = {}
    seeing = i.stale <= 0.0          # never give capacity back on a blind sense; expanding stays allowed (the safe side)
    for o, th in THETA.items():
        ok = calm >= th and i.slo_clean and seeing
        org[o] = {"expand": not sec, "contract": ok, "step": calm if ok else 0.0}
    cf_lo = 1.0 - 0.35 * calm; gp_lo = 1.0 - 0.30 * calm
    cf_hi = 1.0 - 0.35 * excess if hot else 1.0; gp_hi = 1.0 - 0.35 * excess if hot else 1.0
    org["cpufreq"]["envelope"] = in_band(min(cf_lo, cf_hi), cf_hi)
    org["gpu"]["envelope"] = in_band(min(gp_lo, gp_hi), gp_hi)
    org["power"]["envelope"] = in_band(0.65, 1.0)
    # routing is an amount moved, not a level: it may move nothing, never more than the band's top
    org["routing"]["envelope"] = [0.0, min(BAND[1], 0.5 * calm) if not sec else 0.0]
    org["cooling"] = {"expand": True, "protective": True, "contract": calm >= 0.3 and seeing, "step": calm, "envelope": [18.0, 18.0 + 9.0 * calm]}
    org["batch"] = {"expand": (not sec) and seeing and calm >= 0.5 and i.power_stress < 0.9, "contract": True, "protective_contract": True,
                    "admit": (not sec) and seeing and calm >= 0.5 and i.power_stress < 0.9,
                    "pause": sc["sigma"] > 1.0 or i.power_stress >= 0.95 or hot, "step": calm}
    org["rollback"] = {"expand": False, "contract": False, "authorized": bool(i.rollback or sec), "step": 0.0}
    return {"execute": i.mode == "autopilot", "killed": False, "security_hold": sec, "scalars": sc, "organs": org}


def from_governor(g, obs: Dict[str, Any], d: Dict[str, Any] = None, mode: str = None) -> Dict[str, Any]:
    """Authority from a live omnicompass.adapter.Governor after its step (d = the step's directive)."""
    x = g.x; p = g.p; L = g.law
    return authority(NervousInputs(
        E=x.E, U=x.U, I_U=x.I_U, S=x.S, push=g.last_push, push_release=getattr(L, "push_release", 0.2),
        U_gate=getattr(L, "U_gate", 0.5), s_eq=stress_equilibrium(p.delta, p.alpha_s, p.beta_s),
        security_block=float(obs.get("security_block", 0.0)), slo_clean=bool(obs.get("slo_clean", True)),
        power_stress=float(obs.get("power_stress", 0.0)), thermal=float(obs.get("thermal", 0.0)),
        rollback=bool((d or {}).get("rollback_authorized", False)), stale=float(obs.get("stale", 0.0)),
        mode=mode or g.mode, killed=g.killed))


def node_release_gate(n: int, per_node_m: float, used_m: float, pending: int, pods_scaling_up: bool,
                      latency_breach_now: bool, rho: float, node_auth: Dict[str, Any],
                      senses_live: bool = True, last_command_landed: bool = True) -> Dict[str, Any]:
    """May the machine organ give one machine back now? Attribution: an organ is held back only by stress it can cause
    or cure. The node organ reads its own engine view (fed with machine-attributable pressure: pods waiting for a
    place), and the release must also pass:
      coordination  pods are not scaling up and latency is not breached now (pods move first; machines never move
                    against them, the rule of the benchmarked coordination)
      headroom      nothing is pending, and after the release the remaining machines run at or below the engine's own
                    utilisation target rho: used / ((n - 1) x per_node) <= rho
      authority     the node organ's own calm, security and stress gates (authority() above) grant contraction
      senses        every declared sense is live (afferent integrity)
      proprioception the node organ's last command landed (efferent feedback: no new order to a muscle that did not
                    carry out the previous one)
    Returns {"ok": bool, "reason": str, "util_after": float}."""
    util_after = used_m / max((n - 1) * per_node_m, 1e-9) if n > 1 else float("inf")
    checks = [("one machine left", n > 1), ("pods waiting", pending == 0), ("pods scaling up", not pods_scaling_up),
              ("latency breached now", not latency_breach_now), (f"util after {util_after:.2f} > rho {rho:.2f}", util_after <= rho),
              ("node organ has no contraction authority", bool(node_auth.get("organs", {}).get("nodes", {}).get("contract", False))),
              ("a sense is blind", senses_live), ("last node command did not land", last_command_landed)]
    failed = [name for name, ok in checks if not ok]
    return {"ok": not failed, "reason": "; ".join(failed) or "release permitted", "util_after": util_after}
