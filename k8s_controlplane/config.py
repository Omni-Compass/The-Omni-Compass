# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Documented defaults for the control-plane replica.

Sources (algorithm, not source code):
  HPA: kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
       default behavior block (scaleUp 0s / 4 pods or 100% per 15s;
       scaleDown 300s / 100% per 15s; tolerance 0.1; sync 15s)
  CA:  Cluster Autoscaler FAQ / cloud-provider defaults
       scan 10s, unneeded 10m, delay-after-add 10m, util threshold 0.5
  Karpenter-lite: WhenEmptyOrUnderutilized + consolidateAfter, not the
       full scheduler/disruption controller.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HPAConfig:
    target: float = 0.70
    min_replicas: int = 20
    max_replicas: int = 500
    tolerance: float = 0.10
    sync_period_s: int = 15
    scale_up_window_s: int = 0
    scale_down_window_s: int = 300
    scale_up_pods: int = 4
    scale_up_percent: int = 100
    scale_up_period_s: int = 15
    scale_down_percent: int = 100
    scale_down_period_s: int = 15


@dataclass
class CAConfig:
    scan_interval_s: int = 10
    unneeded_s: int = 600
    delay_after_add_s: int = 600
    delay_after_delete_s: int = 10
    utilization_threshold: float = 0.50
    max_nodes: int = 40
    min_nodes: int = 8
    max_add_per_scan: int = 2
    max_delete_per_scan: int = 1
    node_ready_s: int = 90


@dataclass
class KarpenterConfig:
    consolidate_after_s: int = 60
    empty_after_s: int = 0
    disruption_budget_frac: float = 0.10
    node_ready_s: int = 45
    max_nodes: int = 40
    min_nodes: int = 8
    max_add_per_scan: int = 4


@dataclass
class MetricsConfig:
    scrape_period_s: int = 15
    report_lag_s: int = 15
    readiness_s: int = 30
    drop_probability: float = 0.0


@dataclass
class PlantConfig:
    dt_s: int = 15
    duration_s: int = 6 * 3600
    initial_nodes: int = 20
    cores_per_node: float = 8.0
    pod_request_cores: float = 0.50
    node_idle_kw: float = 0.38
    node_dynamic_kw: float = 1.12
    pue: float = 1.18
    site_power_kw: float = 33.0
    initial_replicas: int = 100


@dataclass
class HarnessConfig:
    hpa: HPAConfig = field(default_factory=HPAConfig)
    ca: CAConfig = field(default_factory=CAConfig)
    karpenter: KarpenterConfig = field(default_factory=KarpenterConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    plant: PlantConfig = field(default_factory=PlantConfig)
    omni_period_s: int = 300
    omni_law: dict = field(default_factory=dict)
    gate_unneeded_s: int = 240
    gate_delay_add_s: int = 600
    pool: str = "elastic"
    seed: int = 1
    scenario_id: int = 0
    family: str = "normal_variation"
