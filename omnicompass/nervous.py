"""Nervous system: one engine, many muscles.

Each muscle is a connector with five parts (domain map):
  afferent  sense
  engine    shared six-state field (not duplicated)
  efferent  push
  reflex    shield / bounds before push
  kill      return that muscle to its native controller

Status:
  wired     sense and push are executed in this tree
  sensed    telemetry is accepted; push is not issued
  open      connector registered; no plant; no push

This module does not replace adapter.Governor. It sits around it:
afferents merge into the observation vector the governor already understands;
efferents are tagged by muscle so a kill is per-nerve, not a mystery write.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# Fit from the domain map. Advisory muscles never push from this runtime.
DIRECT = "direct"
SUPERVISORY = "supervisory"
ADVISORY = "advisory"
NOT_OURS = "not_omni"

WIRED = "wired"
SENSED = "sensed"
OPEN = "open"


@dataclass(frozen=True)
class Muscle:
    name: str
    family: str
    fit: str
    status: str
    reads: tuple
    pushes: tuple
    reflexes: tuple
    note: str = ""


# Registered nerves. Status is a claim about THIS tree, not a product slide.
CATALOG: List[Muscle] = [
    Muscle("nodes", "infra", DIRECT, WIRED,
           ("load_ratio", "pending", "requests"),
           ("node_delta", "actuation"),
           ("request_floor", "step_limit", "I2", "I5"),
           "fleet + k8s_controlplane"),
    Muscle("hpa", "infra", DIRECT, WIRED,
           ("utilization", "replicas"),
           ("hpa_target",),
           ("target_bounds_50_95",),
           "target write only when authority is on"),
    Muscle("power_cap", "infra", DIRECT, WIRED,
           ("power_stress", "site_limit"),
           ("power_cap",),
           ("I4", "cap_lo_hi"),
           "harness"),
    Muscle("heat", "infra", DIRECT, SENSED,
           ("thermal",),
           (),
           ("thermal_limit",),
           "feeds E/S; no chiller write"),
    Muscle("network", "infra", DIRECT, SENSED,
           ("network_stress",),
           ("route_shift",),
           ("link_capacity",),
           "directive flag only"),
    Muscle("security", "infra", DIRECT, SENSED,
           ("security_block",),
           (),
           ("I1",),
           "blocks expansion"),
    Muscle("gpu", "infra", DIRECT, OPEN,
           ("gpu_util", "gpu_power", "gpu_temp", "gpu_mem"),
           ("gpu_power_cap", "mig_partition"),
           ("temp_limit", "no_kill_midstep"),
           "no GPU plant in this tree"),
    Muscle("cpu_pstate", "infra", DIRECT, OPEN,
           ("rapl_watts",),
           ("pstate",),
           ("latency_floor",)),
    Muscle("memory", "infra", DIRECT, OPEN,
           ("mem_used", "mem_request"),
           ("mem_request",),
           ("oom_margin",)),
    Muscle("storage", "infra", SUPERVISORY, OPEN,
           ("io_load", "io_latency", "capacity"),
           ("tier", "volume_scale"),
           ("durability",)),
    Muscle("batch_queue", "infra", DIRECT, OPEN,
           ("queue_depth", "deadline_s"),
           ("admit", "priority"),
           ("deadline",)),
    Muscle("cooling", "facility", DIRECT, OPEN,
           ("inlet_c", "chiller_load"),
           ("setpoint_c", "fan_curve"),
           ("inlet_limit",)),
    Muscle("grid", "facility", DIRECT, OPEN,
           ("price", "carbon", "demand_signal"),
           ("shed_kw", "shift"),
           ("contract_limit",)),
    Muscle("training", "ai", DIRECT, OPEN,
           ("gpu_power", "step", "progress"),
           ("power_cap", "pack"),
           ("no_kill_midstep",)),
    Muscle("inference", "ai", DIRECT, OPEN,
           ("qps", "latency", "gpu_mem"),
           ("replicas", "batch"),
           ("latency_slo",)),
    Muscle("agent_containment", "ai", DIRECT, OPEN,
           ("actions", "spend", "net"),
           ("cpu_cap", "mem_cap", "net_cap", "spend_cap"),
           ("hard_cap", "instant_kill"),
           "containment only; not value alignment"),
    Muscle("value_alignment", "ai", NOT_OURS, OPEN,
           (),
           (),
           (),
           "not a muscle Omni governs"),
]


def catalog_by_name() -> Dict[str, Muscle]:
    return {m.name: m for m in CATALOG}


def wired() -> List[Muscle]:
    return [m for m in CATALOG if m.status == WIRED]


def open_muscles() -> List[Muscle]:
    return [m for m in CATALOG if m.status == OPEN]


@dataclass
class NerveEvent:
    muscle: str
    kind: str  # sense | push | hold | kill | reflex
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Bundle:
    """One tick of the whole body."""
    obs: Dict[str, float]
    events: List[NerveEvent] = field(default_factory=list)
    kills: List[str] = field(default_factory=list)

    def sense(self, muscle: str, **vals: float) -> None:
        m = catalog_by_name()[muscle]
        for k, v in vals.items():
            self.obs[k] = float(v)
        self.events.append(NerveEvent(muscle, "sense", dict(vals)))
        if m.status == OPEN:
            self.events.append(NerveEvent(muscle, "hold", {"reason": "open"}))

    def kill(self, muscle: str) -> None:
        self.kills.append(muscle)
        self.events.append(NerveEvent(muscle, "kill", {}))


def merge_stack_obs(bundle: Bundle) -> Dict[str, float]:
    """Map extra nerves onto the governor's existing observation names."""
    o = dict(bundle.obs)
    aliases = {
        "utilization": "load_ratio",
        "gpu_util": "load_ratio",
        "inlet_c": "thermal",
        "gpu_temp": "thermal",
        "rapl_watts": "power_stress",
        "gpu_power": "power_stress",
        "queue_depth": "queue_ratio",
        "spend": "queue_ratio",
    }
    for src, dst in aliases.items():
        if src in o and dst not in o:
            x = float(o[src])
            if src == "inlet_c":
                x = max(0.0, (x - 18.0) / 12.0)
            elif src == "gpu_temp":
                x = max(0.0, (x - 40.0) / 40.0)
            o[dst] = x
    return o


def allow_push(muscle: str, authority: bool, killed: List[str]) -> bool:
    m = catalog_by_name()[muscle]
    if muscle in killed:
        return False
    if not authority:
        return False
    if m.fit in (ADVISORY, NOT_OURS):
        return False
    return m.status == WIRED


def tag_directive(d: Dict[str, Any], authority: bool, killed: List[str]) -> Dict[str, Any]:
    """Attach which muscle may execute which field. Unwired fields stay logged."""
    out = dict(d)
    nerves = {
        "node_delta": "nodes",
        "actuation": "nodes",
        "hpa_target": "hpa",
        "power_cap": "power_cap",
        "route_shift": "network",
    }
    permitted = {}
    for field_name, muscle in nerves.items():
        if field_name in out:
            permitted[field_name] = allow_push(muscle, authority, killed)
    out["nerve_permit"] = permitted
    out["nerve_killed"] = list(killed)
    return out
