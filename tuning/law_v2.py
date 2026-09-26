"""Prototype law v2: two structural changes to how the engine's directive becomes actions (adapter.directive_to_actions
is frozen and is not edited; v2 wraps it).

1. Replicas (direct actuation) are sized with the engine's own sizing equation, the one it uses for nodes:
       r* = ceil(r * load / rho* + kq * q * r)
   and may rise whenever there is backlog, not only when the node decision points up.
2. The power cap moves only when the change exceeds a dead-band AND the equation (2) control push has converged
   (|push| <= push_release), the same gate the engine applies to releasing capacity; raising the cap is never delayed.
"""
from __future__ import annotations

import math
from omnicompass import adapter as A

_frozen = A.directive_to_actions
CAP_DEADBAND = 0.05


def directive_to_actions_v2(d, stack_state, proposals, cfg, direct_actuation=False, law=None, push=0.0):
    out = [a for a in _frozen(d, stack_state, proposals, cfg, direct_actuation) if a["action"] not in ("replicas", "power_cap")
           or not direct_actuation and a["action"] == "replicas"]
    if direct_actuation:
        cur_r = int(stack_state["replicas"])
        q = float(d.get("q", 0.0))
        kq = law.kq if law is not None else 0.795
        rt = max(20, min(500, math.ceil(cur_r * float(d["load"]) / max(float(d["demand"]), 1e-9) + kq * q * cur_r)))
        if rt > cur_r or (rt < cur_r and d["node_delta"] <= 0 and q < 0.05):
            out.append({"manager": "Omni-Compass", "action": "replicas", "target": rt, "direction": 1 if rt > cur_r else -1})
    cur = float(stack_state["power_cap"]); cap = float(d["power_cap"])
    if any(a["direction"] > 0 and a["action"] in ("nodes", "terraform_plan", "replicas") for a in out):
        cap = max(cap, cur)
    converged = law is None or abs(push) <= law.push_release
    if cap > cur + 1e-9 or (cur - cap > CAP_DEADBAND and converged):
        out.append({"manager": "Omni-Compass", "action": "power_cap", "target": cap, "direction": -1 if cap < cur else 1})
    return out


class GovernorV2(A.Governor):
    """Frozen Governor; the directive also carries the normalised queue, the control push and the law for v2 actuation."""

    def step(self, obs, conflicts):
        d = super().step(obs, conflicts)
        d["q"] = A.observe_vector(obs, conflicts)["q"]; d["push"] = self.last_push; d["_law"] = self.law
        return d


def install(sb):
    """Switch a stack_benchmark module to v2 actuation; returns an uninstall function."""
    old = (sb.Governor, sb.directive_to_actions)
    sb.Governor = GovernorV2
    sb.directive_to_actions = lambda d, st, props, cfg, direct_actuation=False: directive_to_actions_v2(
        d, st, props, cfg, direct_actuation, d.get("_law"), d.get("push", 0.0))
    def uninstall():
        sb.Governor, sb.directive_to_actions = old
    return uninstall
