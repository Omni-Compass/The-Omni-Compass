# Handoff: where everything is and how to run it

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright and by patents and patent applications. See [`LICENSE`](LICENSE).

The full manual: `docs/OMNI_COMPASS_MANUAL.md` (PDF alongside). Everything below is on `main`. Anyone (a person or another AI) can pick it up from here.

## The engine

| Piece | File | What it is |
|---|---|---|
| Frozen engine | `omnicompass/core.py`, `omnicompass/adapter.py` | the 8-equation core and the governor; unchanged, with its proofs |
| The bowl (new engine layer) | `omnicompass/bowl.py` | one smooth law for every muscle: pull to the middle of the band, push against drift, tanh-bounded, fail up past 95%; and the plug (cover, one restore point, foreign-writer rule) |
| Two-wire GPU governor | `omni_controller/gpu_bowl.py` | the bowl on a real card: clock ceiling (`nvidia-smi -lgc`, up wire) and power limit (`-pl`, down wire) |
| Wire check | `tools/gpu_wire_check.py` | proves both card wires follow, read back and go home before anything runs |
| Realm muscles under the bowl | `realms/bowl_arm.py` | the bowl on every one of the 656 modelled muscles |

## The six organisms

1 Compute (345 muscles) · 2 Physics (262) · 3 Energy (282) · 4 Distribution (337) · 5 the four stacked with every
duplicate kept (1,226) · 6 the whole tower, every muscle once (656). Each is run native, then with Omni on top.

## How to run each benchmark

**Real card + the six organisms with the card inside + card confirmation (Lambda, about 12 hours, one command):**
```
sudo pkill -f gpu_
cd ~/the-omni-compass
git pull
sudo nohup bash scripts/gpu_rented_run.sh > run.log 2>&1 &
tail -f run.log
```
It runs: wire check -> card smoke -> six organisms with the card inside (`tools/run_hil.py`) -> card confirmation, and
ends with `send this one file back: results/gpu/omni-gpu-<stamp>.tar.gz`. Finished when `pgrep -f gpu_rented_run`
prints nothing. Upload that file to GitHub, then terminate the Lambda machine.

**The six organisms, simulated, the 1 / 10 / 100 / 1,000 grid (GitHub, free):** Actions -> `six` -> Run workflow.
Inputs: `runs_per_shard`, `scale` (1, 10, 100, 1000), `shards` (JSON list), `orgs` (JSON list of 1-6), `workers`
(use 1 at 1000x for memory). Total runs = shards x runs_per_shard. The receipt (`SIX.md`) shows the first 1, 10, 100
and 1,000 runs. Examples used: 1,000 runs at 1x = runs_per_shard 100, 10 shards; at 100x = 25 x 40 shards; 100 runs at
1000x = 5 x 20 shards, workers 1. The same grid on any machine: `bash scripts/scale_ladder.sh`.

**Real Kubernetes (GitHub, free, about 1 hour):** Actions -> `benchmark-reps` -> Run workflow, inputs
`duration_s 900`, `arms "native omni"`, `loadgen open`. Set 24 (run 36983865216): machines -32%, p95 -60%, 0 failures.

## Results so far

- Real Kubernetes, sets 23 and 24: about a third fewer machines, responses about 60% faster, zero failed requests.
- Modelled GPU card (`results/sim/gpu_two_wire/`): two-wire bowl +9.0% work per energy, old one-wire +0.1%.
- Six organisms, 1,000 runs at 1x (GitHub): work per energy +0.21% to +0.30%, every knob handed back; time over the
  service line about +0.2 points above native in every organism (not yet a win by the band-first rule).
- The real card on Lambda: running (first valid run on the two-wire engine); results come back as the tar.gz.

## Open work

1. Bring the bowl's time over the service line down to native or below (about +0.2 points today, every organism).
2. 1,000 runs at 1,000x and the two largest organisms at 1,000x need a bigger machine than GitHub's.
3. Kubernetes and the GPU together on one Lambda box (k3s), one set of receipts.
4. The C++ twin of the bowl (the frozen engine already has one, `cpp/`).
