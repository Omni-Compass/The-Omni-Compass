"""Unit + identity tests for the control-plane replica."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from k8s_controlplane.cluster_autoscaler import ClusterAutoscaler
from k8s_controlplane.config import CAConfig, HPAConfig, HarnessConfig
from k8s_controlplane.hpa import HorizontalPodAutoscaler
from k8s_controlplane.benchmark import simulate
from k8s_controlplane.scenarios import generate


def test_hpa_formula_and_tolerance():
    h = HorizontalPodAutoscaler(HPAConfig(target=0.70, min_replicas=1, max_replicas=1000))
    assert h.recommend(50, 0.70) == 50
    assert h.recommend(50, 0.75) == 50  # 75/70 ≈ 1.071, within 10%
    rec = h.recommend(50, 1.40)
    assert rec == 100, rec  # 50 * 2.0
    rec = h.recommend(50, 0.35)
    assert rec == 25, rec


def test_hpa_scale_down_uses_window_max():
    cfg = HPAConfig(target=0.70, min_replicas=1, max_replicas=1000, sync_period_s=15)
    h = HorizontalPodAutoscaler(cfg)
    assert h.step(0, 50, 1.40) == 100
    # metric collapses; scale-down window still holds 100 for 300s
    got = h.step(15, 100, 0.20)
    assert got == 100, got
    got = h.step(315, 100, 0.20)
    assert got < 100, got


def test_hpa_scale_up_rate_limit():
    cfg = HPAConfig(target=0.70, min_replicas=1, max_replicas=1000)
    h = HorizontalPodAutoscaler(cfg)
    got = h.step(0, 10, 7.0)  # wants 100, cap max(4, 100% of 10)=10 → 20
    assert got == 20, got


def test_ca_unneeded_and_delay_after_add():
    ca = ClusterAutoscaler(CAConfig(scan_interval_s=10, unneeded_s=60, delay_after_add_s=60))
    d = ca.step(0, 20, 0, 16, 0.9, 10)
    assert d > 0
    assert ca.step(10, 20, 2, 0, 0.2, 10) == 0
    saw_down = False
    for t in range(20, 200, 10):
        d = ca.step(t, 22, 0, 0, 0.2, 10)
        if t < 60:
            assert d == 0, t
        if d < 0:
            saw_down = True
            break
    assert saw_down


def test_planetlab_traces_load():
    from k8s_controlplane.trace_replay import load_all, resample_hold
    tr = load_all()
    assert len(tr) >= 8, len(tr)
    s = next(iter(tr.values()))
    assert len(s) == 288
    r = resample_hold(s, 300, 15)
    assert len(r) == 288 * 20
    assert r[0] == s[0] and r[19] == s[0] and r[20] == s[1]


def test_omni_down_applies_once_per_period():
    from k8s_controlplane.omni_bridge import OmniLoop
    cfg = HarnessConfig()
    loop = OmniLoop("omni_target_down_hpa70_ca", cfg)
    snap = {"queue_ratio": 0.0, "load_ratio": 0.4, "power_stress": 0.3,
            "thermal": 0.3, "security": 0.0}
    d0 = loop.maybe_step(0, snap, 1.0, 20)
    assert loop.fresh is True
    d1 = loop.maybe_step(15, snap, 1.0, 20)
    assert loop.fresh is False
    assert d1 is d0
    d2 = loop.maybe_step(300, snap, 1.0, 20)
    assert loop.fresh is True


def test_pools_policy():
    from omnicompass.pools import apply_pool
    assert apply_pool({"node_delta": -3}, "always_on")["node_delta"] == 0
    assert apply_pool({"node_delta": -3}, "idle_power")["actuation"] == "park"
    assert apply_pool({"node_delta": -3}, "elastic")["actuation"] == "nodes"


def test_observe_identity():
    cfg = HarnessConfig()
    cfg.plant.duration_s = 30 * 60
    scn = generate(1, 99, cfg.plant.duration_s)[0]
    a = simulate(scn, "hpa70_ca", cfg)
    b = simulate(scn, "omni_observe_hpa70_ca", cfg)
    assert a["trace_hash"] == b["trace_hash"], (a["trace_hash"], b["trace_hash"])


def main():
    test_hpa_formula_and_tolerance()
    print("PASS  HPA formula + 10% tolerance")
    test_hpa_scale_down_uses_window_max()
    print("PASS  HPA scale-down stabilization window")
    test_hpa_scale_up_rate_limit()
    print("PASS  HPA scale-up 4 pods / 100% per 15s")
    test_ca_unneeded_and_delay_after_add()
    print("PASS  CA unneeded + delay-after-add")
    test_planetlab_traces_load()
    print("PASS  PlanetLab traces load + 5min-to-15s hold-last")
    test_omni_down_applies_once_per_period()
    print("PASS  Omni node action only on a fresh period")
    test_pools_policy()
    print("PASS  pool policy always_on / idle_power / elastic")
    test_observe_identity()
    print("PASS  Omni observe bit-identical to HPA+CA")
    print("PASS test_controlplane")


if __name__ == "__main__":
    main()
