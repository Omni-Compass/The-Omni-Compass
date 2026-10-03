# The realms

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

The 656-muscle tower on modelled plants: four realms and the whole tower as a fifth organism, each run natively and
with Omni-Compass on top, with meters and receipts. Evidence class **S** (simulation).

## Run it

```
pip install -r requirements.txt
python3 tools/run_realms.py                      # the preregistered run: 656 muscles and 5 organisms, seeds 1000-1009
python3 tests/test_realms.py                     # the harness's own checks (also inside verify.py)
```

Results: `results/realms/REALMS.md` (the tables), `MUSCLES.csv` (one row per muscle), `REALMS.json` (every per-seed
contrast), `RUN.json` and `SHA256SUMS.txt` (commit and fingerprints).

## What is where

| File | What it is |
|---|---|
| `realms/catalog.csv` | the 656 muscles: family, name, realm, plant, parameter set, knob |
| `tools/realms_catalog.py` | the rules that gave each muscle its realm, plant and knob |
| `realms/plants.py` | the five plants and their native controllers; the four knobs; the capacity law for one plant |
| `realms/presets.py` | every parameter, one set per family class |
| `realms/harness.py` | the arms (native, watch, omni, fixed setpoint), the organisms, the outcome and the label rule |
| `docs/REALMS_PREREGISTRATION.md` | the question, the rules, the seeds and the development history, frozen before the run |

## How it relates to the rest

| Layer | Realm harness | Elsewhere in this repository |
|---|---|---|
| Mathematics (T, V) | uses the frozen engine and governor unchanged | `docs/TRACKING_THEOREM.md`, `verify.py` |
| Simulation (S) | **this** | fleet and cluster simulators, GPU model |
| Real software (L) | not here | set 22 on real Kubernetes (`results/live/LIVE_REPS_22.md`) |
| Physical (P) | not here | the GPU bench: first run on an NVIDIA A10, 2026-10-02 (`results/gpu/run-20261002T082232Z/GPU_REPS.md`); the corrected governor not yet run on a card (`docs/GPU_PREREGISTRATION.md`) |

A realm result that looks good is a reason to test that knob on a real machine, not a substitute for it. The realms
whose knobs can be tested for real first are the compute realm's (the GPU bench, kind), because the tools already
exist.
