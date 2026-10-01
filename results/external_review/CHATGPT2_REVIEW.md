# Review of OmniCompass_GRANDMASTER_ENGINE_HARNESS_PROOF.zip (ChatGPT, second release), 27 September 2026

## New since its first release
- A **graded recovery reflex** in `omnicompass/adapter.py`, ported to C++. It has two thresholds, a threat and a
  severe level. The node addition is gated by sizing, and the power cap is lifted to 100% when the threat is severe.
- **`tools/tower_off_on.py`**: a paired OFF / observe / ON receipt.
- **`FINAL_ENGINEERING_STATUS.md`**. It discloses its own costs honestly: higher peak power, node-hours and round
  trips than OFF.

## Head to head
The same 100 held-out scenarios (seed 360555127) ran on this repository's engine and on ChatGPT's, paired per
scenario with a 95% bootstrap interval. File: `CHATGPT2_GRADED_REFLEX_HEAD_TO_HEAD.txt`.

**Throughput mode (its headline arm).** This engine is better on 6 gauges:
- healthy time;
- physical violations;
- power violations;
- recovery;
- energy;
- peak power.

ChatGPT's is better on 0.

**Protect and direct modes.**

| Gauge | ChatGPT engine vs ours |
|---|---|
| Backlog | about 50% lower |
| Queue | about 40% lower |
| Power violations | 3-6 times higher |
| Heat violations | 35-60 times higher |
| Energy | 4% higher |
| Peak power | about 25% higher |

**Which half of the reflex does the work.** File: `CHATGPT2_REFLEX_SPLIT.txt`.
- **The test.** This engine ran with only the node half of the reflex, without the cap lift.
- **The result.** Protect mode matched this engine on every gauge within the 95% interval. Direct mode gained only
  a tiny average-queue improvement. Throughput mode was unchanged.
- **The conclusion.** All of the reflex's backlog gain comes from lifting the power cap. It is a
  power-and-heat-for-backlog trade, which throughput mode already offers, and throughput mode beats it.
- **Not adopted.**

**Its tower receipt, run on this engine.** `results/tower_off_on/TOWER_OFF_ON_RECEIPT.json`, same seed and
scenarios.
- Observe identity holds in both engines.
- This engine's ON is equal or better on every gauge in the receipt:
  - healthy time: 92.29% vs its 91.97%;
  - recovery: 15.55 min vs 16.35 min;
  - energy: 121.25 kWh vs 121.75 kWh;
  - physical violations: 6.46% vs 6.75%;
  - peak power: 37.21 kW, below OFF, vs its 38.65 kW, above OFF.
- **Adopted:** `tools/tower_off_on.py`, as a convenience receipt.

## A defect it still carries
Its `scripts/kind_bench.sh` still measures latency through `kubectl port-forward` to one pod. That tunnel hangs
when a drain moves the pod, and requests then count as failed only in the arm that drains
(`results/live/LIVE_REPS_PROBE_DEFECT.md`). Any live latency or failed-request figure produced with that script
carries this defect. This repository probes through the Service.
