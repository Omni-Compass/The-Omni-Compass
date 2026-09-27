"""Safety shield: every governor action set is checked against declared invariants before execution.

Invariants (each enforced by construction; every intervention is counted):
  I1 security   no capacity expansion (nodes, Terraform, rollout) while a security block is observed
  I2 bounds     node targets lie in [minimum_nodes, maximum_nodes]; power cap in [0.65, 1.0]. When the current node
                count is itself outside the bounds and the rate limit I5 forbids reaching them in one step, the target
                must move toward the bounds (the only admissible direction): n > max -> max <= t < n, n < min -> n < t <= min
  I3 coherence  an action set never both expands capacity and tightens the power cap
  I4 power      no node addition whose projected power stress exceeds power_limit:
                projected = observed_power_stress * (n + k) / n
  I5 rate       node change per interval bounded by max_node_step

The shield is a runtime monitor: it guarantees the invariants for executed governor actions
under the observed state. It does not certify the plant model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

EXPAND = ("nodes", "terraform_plan", "rollout", "replicas")


@dataclass(frozen=True)
class ShieldLimits:
    power_limit: float = 1.00
    max_node_step: int = 4
    cap_lo: float = 0.65
    cap_hi: float = 1.00


def violations(actions: List[Dict[str, Any]], st: Dict[str, Any], obs: Dict[str, float], cfg,
               lim: ShieldLimits = ShieldLimits()) -> List[str]:
    """Invariants violated by an action set (used to score every arm identically)."""
    v = []
    n = max(1, int(st["actual_nodes"]))
    sec = float(obs.get("security_block", 0.0)) > 0.5
    for a in actions:
        k, t, d = a["action"], a.get("target"), a.get("direction", 0)
        if sec and d > 0 and k in ("nodes", "terraform_plan", "rollout"):
            v.append("I1")
        if k == "nodes":
            ti = int(t)
            inside = cfg.minimum_nodes <= ti <= cfg.maximum_nodes
            toward = (n > cfg.maximum_nodes and cfg.maximum_nodes <= ti < n) or (n < cfg.minimum_nodes and n < ti <= cfg.minimum_nodes)
            if not inside and not toward:
                v.append("I2")
            add = int(t) - n
            if abs(add) > lim.max_node_step:
                v.append("I5")
            if add > 0 and float(obs.get("power_stress", 0.0)) * (n + add) / n > lim.power_limit:
                v.append("I4")
        if k == "power_cap" and not lim.cap_lo <= float(t) <= lim.cap_hi:
            v.append("I2")
    up = any(a.get("direction", 0) > 0 and a["action"] in EXPAND for a in actions)
    tighten = any(a["action"] == "power_cap" and float(a["target"]) < float(st["power_cap"]) - 1e-9 for a in actions)
    if up and tighten:
        v.append("I3")
    return v


def enforce(actions: List[Dict[str, Any]], st: Dict[str, Any], obs: Dict[str, float], cfg,
            lim: ShieldLimits = ShieldLimits()) -> Tuple[List[Dict[str, Any]], int]:
    """Return the largest invariant-satisfying subset/modification of the action set and the intervention count."""
    n = max(1, int(st["actual_nodes"]))
    sec = float(obs.get("security_block", 0.0)) > 0.5
    ps = float(obs.get("power_stress", 0.0))
    out, hits = [], 0
    for a in actions:
        a = dict(a)
        k = a["action"]
        if sec and a.get("direction", 0) > 0 and k in ("nodes", "terraform_plan", "rollout"):
            hits += 1
            continue
        if k == "nodes":
            r = int(a["target"])
            toward = (n > cfg.maximum_nodes and cfg.maximum_nodes <= r < n) or (n < cfg.minimum_nodes and n < r <= cfg.minimum_nodes)
            t = r if toward else max(cfg.minimum_nodes, min(cfg.maximum_nodes, r))   # minimal intervention
            t = max(n - lim.max_node_step, min(n + lim.max_node_step, t))
            if t > n and ps > 0.0:
                k_max = int((lim.power_limit / ps) * n - n + 1e-9)
                t = min(t, n + max(0, k_max))
            if sec and t > n:
                hits += 1          # I1 after clamping: a clamp may turn a request into an expansion; not during a hold
                continue
            if t != int(a["target"]):
                hits += 1
            if t == n:
                continue
            a["target"], a["direction"] = t, (1 if t > n else -1)
        if k == "power_cap":
            c = max(lim.cap_lo, min(lim.cap_hi, float(a["target"])))
            if c != float(a["target"]):
                hits += 1
            a["target"] = c
        out.append(a)
    up = any(a.get("direction", 0) > 0 and a["action"] in EXPAND for a in out)
    if up:
        kept = []
        for a in out:
            if a["action"] == "power_cap" and float(a["target"]) < float(st["power_cap"]) - 1e-9:
                hits += 1
                continue
            kept.append(a)
        out = kept
    return out, hits
