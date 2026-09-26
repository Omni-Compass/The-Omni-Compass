"""Pool actuation policy. Does not change the frozen allocation law.

elastic     node off is allowed (HPA+CA cattle)
always_on   node off is illegal (GPU / pet). Negative node_delta is dropped.
idle_power  negative node_delta becomes park (Ready, idle watts), not power-off.

Pack profiles are overlays on rho0 only. Frozen law stays at rho0=0.914.
"""
from __future__ import annotations

from typing import Any, Dict

POOLS = ("elastic", "always_on", "idle_power")

PACK_MID = {"rho0": 0.82}
PACK_HARD = {"rho0": 0.95}


def apply_pool(directive: Dict[str, Any], pool: str) -> Dict[str, Any]:
    if pool not in POOLS:
        raise ValueError(pool)
    d = dict(directive)
    delta = int(d.get("node_delta", 0))
    if pool == "always_on":
        if delta < 0:
            d["node_delta"] = 0
        d["actuation"] = "hold"
    elif pool == "idle_power" and delta < 0:
        d["actuation"] = "park"
    else:
        d["actuation"] = "nodes" if delta != 0 else "hold"
    d["pool"] = pool
    return d
