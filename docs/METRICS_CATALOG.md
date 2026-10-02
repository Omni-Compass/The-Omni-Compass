# Omni-Compass metrics catalog

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Every gauge Omni-Compass produces, where it comes from, and what kind of number it is. Three kinds:

- **Measured**: read from a real system (a real Kubernetes cluster, a real GPU's own meter, a real wall plug).
- **Modelled**: computed by a simulation from declared physics or recorded traces. It shows the mechanism, not a
  measurement.
- **Internal**: Omni-Compass's own state and decisions, recorded in its audit log on every decision, live or simulated.

Every report says which kind each number is. A modelled number is never presented as a measured one.

---

## 1. Service: what the customer feels

| Gauge | Unit | Where | Kind |
|---|---|---|---|
| Response time, mean / 95th / 99th percentile | ms | live Kubernetes (`tools/live_reps.py`), GPU bench (`tools/gpu_reps.py`), GPU sims | measured live; modelled in sims |
| Failed requests | % | live Kubernetes | measured |
| Requests served / not served | count | GPU bench, GPU sims | measured / modelled |
| Pod start wait, total and mean | s | live Kubernetes (API server creation-to-Ready) | measured |
| Pending pods | pod-minutes | live Kubernetes | measured |
| Backlog (SLO breach) minutes | min | site and node exchange sims, stack benchmark | modelled |
| 95th-percentile latency factor | × | site and node exchange sims | modelled |
| Availability, time healthy, recovery minutes, recovered | share, min | stack benchmark (`benchmarks/stack_benchmark.py`) | modelled |
| SLA violations (physical, total, backlog, power, heat) | share of time | stack benchmark | modelled |

## 2. Work and capacity: what the operator gets for the money

| Gauge | Unit | Where | Kind |
|---|---|---|---|
| **Work per energy** (served requests per kJ) | req/kJ | GPU bench (the preregistered primary outcome), GPU sims | measured / modelled |
| Work per wall energy (whole machine) | req/kJ | GPU bench with a smart plug (`tools/wall_meter.py`) | measured |
| Work served | work units | site and node exchange sims | modelled |
| Work per kWh | units/kWh | node exchange sim | modelled |
| Energy per served request | J | GPU bench | measured |
| Energy per core-hour | Wh | live Kubernetes | declared model |
| CPU used by the app | cores | live Kubernetes (`kubectl top`) | measured |
| Utilisation (used / allocatable) | share | live Kubernetes | measured |
| Replicas (HPA), mean | count | live Kubernetes | measured |
| Pods started | count | live Kubernetes | measured |
| Worker nodes in service, node-hours, idle node-hours | count, h | live Kubernetes, stack benchmark | measured / modelled |

## 3. Energy and power: the bill and the building

| Gauge | Unit | Where | Kind |
|---|---|---|---|
| GPU energy (the device's own `power.draw`, integrated) | J | GPU bench | measured |
| GPU mean power | W | GPU bench, GPU sims | measured / modelled |
| CPU package energy (RAPL) | J | GPU bench, where the machine exposes RAPL | measured |
| Whole-machine energy at the wall | J | GPU bench with a smart plug | measured |
| Energy on kind | Wh | live Kubernetes | **declared model** (kind has no meter) |
| Energy | kWh | site, node exchange and stack sims | modelled |
| Peak power | kW | site and node exchange sims, stack benchmark | modelled |
| **Site-budget violation minutes** (time over the building's limit) | min | site and node exchange sims | modelled |
| GPU power limit, mean; power-limit writes | W, count | GPU bench, GPU sims | measured / modelled |
| Power-cap travel | share | stack benchmark | modelled |

## 4. Hardware: heat and wear

| Gauge | Unit | Where | Kind |
|---|---|---|---|
| GPU temperature, peak and mean | °C | GPU bench, GPU sims | measured / modelled |
| Heat-over minutes | min | hardware plant sim (`hardware/plant.py`) | modelled |
| Thermal travel | share | stack benchmark | modelled |
| Machine round trips, node starts and stops, scale reversals | count | stack benchmark | modelled |

Lower power and fewer temperature swings are the conditions for longer hardware life. **No hardware life extension is
claimed** until real temperature, duty-cycle and wear records exist.

## 5. Battery equivalent (derived)

A battery holds a fixed amount of energy, so battery life follows directly from work per energy:

- runtime on the same charge, for the same work: × (native energy ÷ Omni-Compass energy)
- work on the same charge: × (Omni-Compass work per energy ÷ native work per energy)

Example: the modelled GPU card at +5.1% work per kJ (`results/gpu/sim/after`) does 5.1% more work on one charge.
The same rule turns any measured work-per-energy result into a battery figure. On-site battery banks as an organ of
the power budget are designed (`docs/DOMAIN_MAP.md`, "on-site batteries") and not yet built.

## 6. Safety and control: proof it behaved

| Gauge | Where | Kind |
|---|---|---|
| Writes executed per arm (native 0, watch 0, Omni-Compass n) | GPU bench, live Kubernetes | measured |
| Every arm ended at its start setting (the kill switch restored it) | GPU bench, live Kubernetes switch drill | measured |
| Invariant violations (all, and excluding power) | stack benchmark | modelled |
| Security violations, contradictions, pages | stack benchmark | modelled |
| Freeze check: code hashes at start and end (confirmation runs) | GPU bench (`FREEZE.json`, `FREEZE_END.json`) | measured |
| SHA-256 of every raw file | every live run | measured |
| The seal: every Python/C++ twin unchanged since proven equal | `results/SEAL.json`, `verify.py` | checked on every build |

## 7. Internal: Omni-Compass's own state, on every decision (audit log)

| Field | Meaning |
|---|---|
| `E, U, I_U, S, B, B_dot` | the six-state engine: energy, coherence (health), unmet-need integral, stress, redistribution, its rate |
| `state_observed`, `state_projected_next`, `prediction_error` | what the device said, what the engine projected, and how far off the last projection was |
| `requested_cap`, `granted_cap`, `shield_bound`, `want_w` | what the engine asked for, what the shield allowed, which bound decided it, the limit written |
| `admissible` | whether the engine was permitted to change anything this decision |
| `speed_lock` (`ratios`, `line`, `aim`, `rate`) | the speed lock's reading against the run without Omni-Compass |
| `convey` engaged / released | when idle CPU is conveyed to serving pods, and when it is given back |
| `authority`: `calm` and its scalars (`kappa, h, sigma, nu`), `execute`, `contract` per organ, and the machine organ's own view | how settled the engine is, whether it may act at all, and which organs may give capacity back this decision (Kubernetes controller; `omnicompass/nervous_system.py`) |
| compass readings | the direction the engine reads the whole system to be moving (`omnicompass/compass.py`) |
| `write`, `would_write`, `why` | every command sent (or, in watch mode, withheld) and its reason |
| `snapshot`, `restored` | every setting read at start, and its read-back after the kill switch |

## 8. Where each report lives

| Report | Command | Output |
|---|---|---|
| Live Kubernetes, paired | `benchmark-reps.yml` (commit with `[reps]`) | `LIVE_REPS.md`, `results/live/` |
| GPU bench on a real card | `sudo bash scripts/gpu_paired.sh` | `results/gpu/run-*/GPU_REPS.md` |
| GPU physics sim | `python3 tools/gpu_physics_sim.py` | `results/gpu/sim/` |
| CPU-then-GPU speed lock sim | `python3 tools/gpu_pipeline_sim.py` | `results/gpu/sim/pipeline/` |
| Site power exchange (GPU groups) | `python3 hardware/site_exchange.py` | `results/hardware/SITE_EXCHANGE_*.json` |
| CPU + GPU on one budget | `python3 hardware/node_exchange.py` | `results/hardware/NODE_EXCHANGE_*.json` |
| Full stack benchmark and every check | `python3 verify.py` | `results/`, `VERIFICATION: PASS` |
