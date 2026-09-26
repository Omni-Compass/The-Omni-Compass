"""One harness, three pools, same arms. Elastic / always-on / idle-power."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .benchmark import simulate
from .config import HarnessConfig
from .scenarios import generate

POOLS = ("elastic", "always_on", "idle_power")
ARMS = (
    "hpa70_ca",
    "omni_observe_hpa70_ca",
    "omni_target_hpa70_ca",
    "omni_target_gate_hpa70_ca",
)
KEYS = (
    "energy_kwh",
    "time_healthy",
    "availability",
    "machines_started",
    "machines_stopped",
    "recovery_minutes",
)


def run_suite(scenarios: int = 8, seed: int = 424242) -> dict:
    scns = generate(scenarios, seed, 6 * 3600)
    rows = []
    for pool in POOLS:
        for arm in ARMS:
            cfg = HarnessConfig(seed=seed)
            cfg.pool = pool
            if arm == "omni_target_hpa70_ca":
                cfg.omni_law = {"rho0": 0.82}
            if arm == "omni_target_gate_hpa70_ca":
                cfg.omni_law = {"rho0": 0.95}
            for sc in scns:
                rec = simulate(sc, arm, cfg)
                rec["pool"] = pool
                rows.append(rec)
    board = {}
    for pool in POOLS:
        board[pool] = {}
        for arm in ARMS:
            sub = [r for r in rows if r["pool"] == pool and r["arm"] == arm]
            board[pool][arm] = {k: float(np.mean([r[k] for r in sub])) for k in KEYS}
    out = Path(__file__).resolve().parent / "results" / "SUITE.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"scenarios": scenarios, "seed": seed, "board": board, "n_rows": len(rows)}
    out.write_text(json.dumps(payload, indent=2))
    return payload


def main():
    p = run_suite()
    for pool, arms in p["board"].items():
        print(f"== {pool} ==")
        for arm, m in arms.items():
            print(
                f"  {arm:28} E={m['energy_kwh']:.1f} H={m['time_healthy']:.3f} "
                f"st={m['machines_started']:.1f}/{m['machines_stopped']:.1f}"
            )


if __name__ == "__main__":
    main()
