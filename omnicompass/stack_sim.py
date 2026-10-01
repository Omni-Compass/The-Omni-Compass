"""Synthetic fragmented-stack model: proposal behaviour of Kubernetes, Terraform, HPA/VPA,
Karpenter, Argo CD/Rollouts, Istio/Cilium, power/thermal, alerting and paging roles.

Each block is extracted verbatim from reference/omni_compass_reference_engine.py at the line shown.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import numpy as np

# --- source line 21897: ManagerBenchmarkConfig
@dataclass
class ManagerBenchmarkConfig:
    profile: str = "core"
    scenarios: int = 500
    steps: int = 48
    interval_minutes: int = 5
    initial_nodes: int = 20
    minimum_nodes: int = 8
    maximum_nodes: int = 40
    capacity_units_per_node: float = 100.0
    site_power_limit_kw: float = 33.0
    pue: float = 1.18
    node_idle_kw: float = 0.38
    node_dynamic_kw: float = 1.12
    terraform_apply_delay_steps: int = 8
    grafana_refresh_steps: int = 2
    datadog_eval_steps: int = 3
    prometheus_eval_steps: int = 2
    certification_streak: int = 4

    @property
    def dt_hours(self) -> float:
        return float(self.interval_minutes / 60.0)

# --- source line 21922: ManagerScenario
@dataclass
class ManagerScenario:
    scenario_id: int
    seed: int
    family: str
    event_start: int
    event_duration: int
    base_load_fraction: float
    spike_multiplier: float
    failed_node_fraction: float
    telemetry_delay_steps: int
    telemetry_loss_probability: float
    network_efficiency_drop: float
    power_derate: float
    security_block_probability: float
    rollout_multiplier: float
    kafka_lag_steps: int
    alert_noise_probability: float
    batch_pressure_fraction: float
    operator_delay_steps: int

# --- source line 22021: _mom_clamp
def _mom_clamp(x: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, x)))

# --- source line 22007: _MOM_FAMILY_WEIGHTS
_MOM_FAMILY_WEIGHTS = [
    ("normal_variation", 0.10),
    ("demand_spike", 0.14),
    ("node_rack_failure", 0.12),
    ("telemetry_fault", 0.12),
    ("kubernetes_terraform_conflict", 0.12),
    ("alert_incident", 0.10),
    ("power_thermal_network", 0.12),
    ("security_policy", 0.08),
    ("deployment_rollout", 0.06),
    ("compound_failure", 0.04),
]

# --- source line 22025: _mom_allocate_families
def _mom_allocate_families(n: int) -> List[str]:
    n = max(1, int(n))
    raw = [(name, n * weight) for name, weight in _MOM_FAMILY_WEIGHTS]
    counts = {name: int(math.floor(value)) for name, value in raw}
    remainder = n - sum(counts.values())
    order = sorted(raw, key=lambda item: (item[1] - math.floor(item[1])), reverse=True)
    for i in range(remainder):
        counts[order[i % len(order)][0]] += 1
    families: List[str] = []
    for name, _ in _MOM_FAMILY_WEIGHTS:
        families.extend([name] * counts[name])
    return families[:n]

# --- source line 22039: _mom_generate_scenarios
def _mom_generate_scenarios(cfg: ManagerBenchmarkConfig, seed_base: int) -> List[ManagerScenario]:
    families = _mom_allocate_families(cfg.scenarios)
    scenarios: List[ManagerScenario] = []
    for idx, family in enumerate(families):
        seed = int(seed_base) + idx * 1009 + 17
        rng = np.random.default_rng(seed)
        event_start = int(rng.integers(max(4, cfg.steps // 8), max(5, cfg.steps // 2)))
        event_duration = int(rng.integers(max(4, cfg.steps // 10), max(6, cfg.steps // 3)))
        values = {
            "spike_multiplier": 1.0,
            "failed_node_fraction": 0.0,
            "telemetry_delay_steps": int(rng.integers(0, 2)),
            "telemetry_loss_probability": float(rng.uniform(0.0, 0.015)),
            "network_efficiency_drop": 0.0,
            "power_derate": 1.0,
            "security_block_probability": 0.0,
            "rollout_multiplier": 1.0,
            "kafka_lag_steps": int(rng.integers(0, 2)),
            "alert_noise_probability": float(rng.uniform(0.0, 0.02)),
            "batch_pressure_fraction": float(rng.uniform(0.02, 0.10)),
        }
        if family == "demand_spike":
            values["spike_multiplier"] = float(rng.uniform(1.55, 2.35))
            values["batch_pressure_fraction"] = float(rng.uniform(0.12, 0.32))
        elif family == "node_rack_failure":
            values["failed_node_fraction"] = float(rng.uniform(0.12, 0.38))
        elif family == "telemetry_fault":
            values["telemetry_delay_steps"] = int(rng.integers(3, 9))
            values["telemetry_loss_probability"] = float(rng.uniform(0.10, 0.35))
            values["kafka_lag_steps"] = int(rng.integers(2, 7))
        elif family == "kubernetes_terraform_conflict":
            values["spike_multiplier"] = float(rng.uniform(1.30, 1.85))
            values["rollout_multiplier"] = float(rng.uniform(1.10, 1.35))
        elif family == "alert_incident":
            values["alert_noise_probability"] = float(rng.uniform(0.14, 0.38))
            values["telemetry_delay_steps"] = int(rng.integers(1, 5))
        elif family == "power_thermal_network":
            values["network_efficiency_drop"] = float(rng.uniform(0.18, 0.45))
            values["power_derate"] = float(rng.uniform(0.68, 0.86))
            values["spike_multiplier"] = float(rng.uniform(1.20, 1.65))
        elif family == "security_policy":
            values["security_block_probability"] = float(rng.uniform(0.38, 0.82))
            values["rollout_multiplier"] = float(rng.uniform(1.10, 1.30))
        elif family == "deployment_rollout":
            values["rollout_multiplier"] = float(rng.uniform(1.30, 1.80))
            values["spike_multiplier"] = float(rng.uniform(1.10, 1.40))
        elif family == "compound_failure":
            values["spike_multiplier"] = float(rng.uniform(1.55, 2.25))
            values["failed_node_fraction"] = float(rng.uniform(0.12, 0.30))
            values["telemetry_delay_steps"] = int(rng.integers(3, 8))
            values["telemetry_loss_probability"] = float(rng.uniform(0.10, 0.28))
            values["network_efficiency_drop"] = float(rng.uniform(0.15, 0.40))
            values["power_derate"] = float(rng.uniform(0.70, 0.88))
            values["security_block_probability"] = float(rng.uniform(0.12, 0.42))
            values["rollout_multiplier"] = float(rng.uniform(1.15, 1.55))
            values["kafka_lag_steps"] = int(rng.integers(2, 7))
            values["alert_noise_probability"] = float(rng.uniform(0.08, 0.24))
            values["batch_pressure_fraction"] = float(rng.uniform(0.15, 0.35))
        scenarios.append(ManagerScenario(
            scenario_id=idx + 1,
            seed=seed,
            family=family,
            event_start=event_start,
            event_duration=event_duration,
            base_load_fraction=float(rng.uniform(0.52, 0.76)),
            operator_delay_steps=int(rng.integers(2, 9)),
            **values,
        ))
    return scenarios

# --- source line 22123: _mom_event_active
def _mom_event_active(scenario: ManagerScenario, step: int) -> bool:
    return scenario.event_start <= step < (scenario.event_start + scenario.event_duration)

# --- source line 22127: _mom_source_signals
def _mom_source_signals(scenario: ManagerScenario, step: int, cfg: ManagerBenchmarkConfig, rng: np.random.Generator) -> Dict[str, float]:
    phase = 2.0 * math.pi * step / max(1, cfg.steps)
    demand = scenario.base_load_fraction * (0.88 + 0.14 * math.sin(phase - 0.7))
    demand *= float(rng.lognormal(mean=-0.5 * 0.035**2, sigma=0.035))
    active = _mom_event_active(scenario, step)
    if active:
        demand *= scenario.spike_multiplier
    batch = scenario.batch_pressure_fraction * (1.0 + 0.35 * math.sin(phase * 1.7 + 0.5))
    if active and scenario.family in ("demand_spike", "compound_failure"):
        batch *= 1.65
    failed_fraction = scenario.failed_node_fraction if active else 0.0
    network_efficiency = 1.0 - (scenario.network_efficiency_drop if active else 0.0)
    power_derate = scenario.power_derate if active else 1.0
    security_block = bool(active and rng.random() < scenario.security_block_probability)
    rollout = scenario.rollout_multiplier if active and scenario.family in ("kubernetes_terraform_conflict", "deployment_rollout", "security_policy", "compound_failure") else 1.0
    return {
        "demand_fraction": float(max(0.0, demand)),
        "batch_fraction": float(max(0.0, batch)),
        "failed_fraction": float(failed_fraction),
        "network_efficiency": float(_mom_clamp(network_efficiency, 0.40, 1.0)),
        "power_derate": float(_mom_clamp(power_derate, 0.55, 1.0)),
        "security_block": float(1.0 if security_block else 0.0),
        "rollout_multiplier": float(rollout),
        "event_active": float(1.0 if active else 0.0),
        "telemetry_drop": float(1.0 if rng.random() < scenario.telemetry_loss_probability else 0.0),
        "alert_noise_datadog": float(1.0 if rng.random() < scenario.alert_noise_probability else 0.0),
        "alert_noise_prometheus": float(1.0 if rng.random() < scenario.alert_noise_probability * 0.85 else 0.0),
    }

# --- source line 22157: _mom_delayed_observation
def _mom_delayed_observation(history: List[Dict[str, float]], delay_steps: int) -> Dict[str, float]:
    if not history:
        return {}
    idx = max(0, len(history) - 1 - max(0, int(delay_steps)))
    return dict(history[idx])

# --- source line 22164: _mom_proposals
def _mom_proposals(state: Dict[str, Any], obs: Dict[str, float], scenario: ManagerScenario, step: int, cfg: ManagerBenchmarkConfig, noise_flags: Dict[str, float]) -> List[Dict[str, Any]]:
    proposals: List[Dict[str, Any]] = []
    actual_nodes = int(state["actual_nodes"])
    queue_ratio = float(obs.get("queue_ratio", 0.0))
    load_ratio = float(obs.get("load_ratio", 0.0))
    thermal = float(obs.get("thermal", 0.0))
    power_stress = float(obs.get("power_stress", 0.0))
    network_stress = float(obs.get("network_stress", 0.0))
    stale = bool(obs.get("stale", 0.0) > 0.5)
    security_block = bool(obs.get("security_block", 0.0) > 0.5)
    rollout = float(obs.get("rollout_multiplier", 1.0))

    hpa_target = int(round(state["replicas"] * _mom_clamp(0.90 + 0.55 * load_ratio + 0.45 * queue_ratio, 0.65, 1.65)))
    hpa_target = max(20, min(500, hpa_target))
    if hpa_target != state["replicas"]:
        proposals.append({"manager":"HPA/VPA", "action":"replicas", "target":hpa_target, "direction":1 if hpa_target > state["replicas"] else -1})

    effective_need = max(load_ratio, queue_ratio + 0.70)
    karp_target = int(math.ceil(actual_nodes * _mom_clamp(effective_need, 0.55, 1.65)))
    karp_target = max(cfg.minimum_nodes, min(cfg.maximum_nodes, karp_target))
    if queue_ratio > 0.25:
        karp_target = min(cfg.maximum_nodes, max(karp_target, actual_nodes + 1))
    elif queue_ratio < 0.05 and load_ratio < 0.63:
        karp_target = max(cfg.minimum_nodes, min(karp_target, actual_nodes - 1))
    if karp_target != actual_nodes:
        proposals.append({"manager":"Karpenter", "action":"nodes", "target":karp_target, "direction":1 if karp_target > actual_nodes else -1})

    sustained = float(state["smoothed_load"])
    tf_target = int(math.ceil(cfg.initial_nodes * _mom_clamp(0.72 + 0.55 * sustained + 0.35 * queue_ratio, 0.55, 1.70)))
    tf_target = max(cfg.minimum_nodes, min(cfg.maximum_nodes, tf_target))
    if scenario.family == "kubernetes_terraform_conflict" and _mom_event_active(scenario, step):
        tf_target = max(cfg.minimum_nodes, min(cfg.maximum_nodes, tf_target + (2 if step % 2 == 0 else -2)))
    if tf_target != state["terraform_desired_nodes"]:
        proposals.append({"manager":"Terraform", "action":"terraform_plan", "target":tf_target, "direction":1 if tf_target > state["terraform_desired_nodes"] else -1})

    if rollout > 1.05:
        proposals.append({"manager":"Argo CD / Rollouts", "action":"rollout", "target":rollout, "direction":1})
        if thermal > 0.95 or power_stress > 1.0 or security_block:
            proposals.append({"manager":"Argo CD / Rollouts", "action":"rollback", "target":1.0, "direction":-1})

    if thermal > 0.86 or power_stress > 0.93:
        cap = _mom_clamp(1.0 - 0.22 * max(thermal - 0.80, power_stress - 0.86), 0.70, 0.98)
        proposals.append({"manager":"Power/Thermal", "action":"power_cap", "target":cap, "direction":-1})

    if network_stress > 0.18:
        proposals.append({"manager":"Istio/Cilium", "action":"route_shift", "target":_mom_clamp(network_stress, 0.0, 1.0), "direction":1})

    if security_block:
        proposals.append({"manager":"Vault/OPA", "action":"deny_change", "target":1.0, "direction":-1})

    warning = queue_ratio > 0.20 or thermal > 0.82 or power_stress > 0.90 or network_stress > 0.25
    critical = queue_ratio > 0.48 or thermal > 0.98 or power_stress > 1.02
    if warning or noise_flags.get("alert_noise_datadog", 0.0) > 0.5:
        proposals.append({"manager":"Datadog", "action":"alert", "target":2 if critical else 1, "direction":1})
    if warning or noise_flags.get("alert_noise_prometheus", 0.0) > 0.5:
        proposals.append({"manager":"Prometheus/Alertmanager", "action":"alert", "target":2 if critical else 1, "direction":1})
    if critical and not stale:
        proposals.append({"manager":"PagerDuty", "action":"page", "target":1, "direction":1})

    if obs.get("batch_fraction", 0.0) > 0.15:
        proposals.append({"manager":"Slurm/Ray/Kueue", "action":"batch_admission", "target":obs.get("batch_fraction", 0.0), "direction":1})
    return proposals

# --- source line 22228: _mom_conflict_count
def _mom_conflict_count(proposals: List[Dict[str, Any]]) -> Tuple[int, int]:
    conflicts = 0
    duplicate_alerts = 0
    node_dirs = [p["direction"] for p in proposals if p["action"] in ("nodes", "terraform_plan")]
    replica_dirs = [p["direction"] for p in proposals if p["action"] == "replicas"]
    rollout_dirs = [p["direction"] for p in proposals if p["action"] in ("rollout", "rollback")]
    if node_dirs and min(node_dirs) < 0 < max(node_dirs):
        conflicts += 1
    if replica_dirs and min(replica_dirs) < 0 < max(replica_dirs):
        conflicts += 1
    if rollout_dirs and min(rollout_dirs) < 0 < max(rollout_dirs):
        conflicts += 1
    has_scale_up = any(p["direction"] > 0 and p["action"] in ("nodes", "terraform_plan", "replicas", "rollout") for p in proposals)
    has_cap = any(p["action"] == "power_cap" for p in proposals)
    has_deny = any(p["action"] == "deny_change" for p in proposals)
    if has_scale_up and has_cap:
        conflicts += 1
    if has_scale_up and has_deny:
        conflicts += 1
    alerts = [p for p in proposals if p["action"] == "alert"]
    if len(alerts) > 1:
        duplicate_alerts = len(alerts) - 1
        conflicts += 1
    return int(conflicts), int(duplicate_alerts)
