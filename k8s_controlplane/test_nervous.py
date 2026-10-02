# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Nervous-system unit checks. No live cluster."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omnicompass.nervous import (
    CATALOG,
    NOT_OURS,
    WIRED,
    Bundle,
    allow_push,
    merge_stack_obs,
    tag_directive,
    wired,
)


def test_catalog_has_body_and_a_not_ours():
    names = {m.name for m in CATALOG}
    assert {"nodes", "hpa", "power_cap", "gpu", "cooling", "agent_containment"} <= names
    assert any(m.fit == NOT_OURS for m in CATALOG)
    assert {m.name for m in wired()} == {"nodes", "hpa", "power_cap", "security", "deployments", "gpu", "cpu_pstate", "batch_queue"}


def test_open_muscle_senses_but_cannot_push():
    b = Bundle(obs={})
    b.sense("memory", mem_used=0.9, mem_request=0.5)
    assert allow_push("memory", authority=True, killed=[]) is False
    assert any(e.kind == "hold" for e in b.events)


def test_kill_blocks_even_wired():
    assert allow_push("nodes", True, []) is True
    assert allow_push("nodes", True, ["nodes"]) is False
    assert allow_push("nodes", False, []) is False


def test_merge_maps_facility_onto_stack_channels():
    b = Bundle(obs={})
    b.sense("cooling", inlet_c=30.0)
    o = merge_stack_obs(b)
    assert "thermal" in o and o["thermal"] > 0


def test_tag_directive_observe_denies_writes():
    d = tag_directive({"node_delta": -1, "power_cap": 0.9}, authority=False, killed=[])
    assert d["nerve_permit"]["node_delta"] is False


def main():
    test_catalog_has_body_and_a_not_ours()
    print("PASS  catalog: wired compute, open body, alignment not ours")
    test_open_muscle_senses_but_cannot_push()
    print("PASS  open muscle holds")
    test_kill_blocks_even_wired()
    print("PASS  kill and observe deny push")
    test_merge_maps_facility_onto_stack_channels()
    print("PASS  cooling maps onto thermal afferent")
    test_tag_directive_observe_denies_writes()
    print("PASS  observe tags writes denied")
    print("PASS test_nervous")


if __name__ == "__main__":
    main()
