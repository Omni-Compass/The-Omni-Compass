# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Sweep AllocationLaw + CA gate. Score vs HPA+CA on the same plant."""
from __future__ import annotations

import json
from pathlib import Path

from .benchmark import run
from .config import HarnessConfig

OUT = Path(__file__).resolve().parent / "results"


def eval_arm(name, law, scenarios=8, seed=424242):
    def _run(n, s, out, arms=None):
        cfg = HarnessConfig(seed=s)
        cfg.omni_law = law
        from . import benchmark as bm
        from .scenarios import generate
        from copy import deepcopy
        import numpy as np
        scns = generate(n, s, cfg.plant.duration_s)
        arms = arms or [name]
        rows = [bm.simulate(sc, a, cfg) for sc in scns for a in arms]
        keys = [k for k in rows[0] if k not in ("scenario_id", "family", "arm", "trace_hash")]
        return {k: float(np.mean([r[k] for r in rows])) for k in keys}

    return _run(scenarios, seed, OUT, [name])


def main():
    base = run(8, 424242, OUT / "tune_base", arms=["hpa70_ca"])
    h = base["means"]["hpa70_ca"]
    print("HPA+CA", round(h["energy_kwh"], 3), "health", round(h["time_healthy"], 4))
    grid = [
        ("target_default", "omni_target_hpa70_ca", {}),
        ("gate_default", "omni_target_gate_hpa70_ca", {}),
        ("gate_rho95", "omni_target_gate_hpa70_ca", {"rho0": 0.95}),
        ("gate_rho98", "omni_target_gate_hpa70_ca", {"rho0": 0.98}),
        ("gate_rho95_kE", "omni_target_gate_hpa70_ca", {"rho0": 0.95, "kE": 0.45}),
        ("target_rho95", "omni_target_hpa70_ca", {"rho0": 0.95}),
        ("target_rho98", "omni_target_hpa70_ca", {"rho0": 0.98}),
        ("target_rho95_kE", "omni_target_hpa70_ca", {"rho0": 0.95, "kE": 0.50, "kI": 0.35}),
        ("gate_rho93_kEhi", "omni_target_gate_hpa70_ca", {"rho0": 0.93, "kE": 0.55, "kI": 0.30}),
    ]
    rows = []
    for tag, arm, law in grid:
        m = eval_arm(arm, law)
        gain = 1.0 - m["energy_kwh"] / h["energy_kwh"]
        rec = {
            "tag": tag, "arm": arm, "law": law,
            "energy": m["energy_kwh"],
            "health": m["time_healthy"],
            "avail": m["availability"],
            "starts": m["machines_started"],
            "stops": m["machines_stopped"],
            "recover_min": m["recovery_minutes"],
            "energy_gain": gain,
        }
        rows.append(rec)
        print(f"{tag:18} E={m['energy_kwh']:.2f} H={m['time_healthy']:.3f} "
              f"gain={gain*100:.1f}% starts={m['machines_started']:.1f}")
    (OUT / "TUNE.json").write_text(json.dumps({"baseline": h, "rows": rows}, indent=2, default=float))


if __name__ == "__main__":
    main()
