# How to Read the Results

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

This chapter teaches you to read every table Omni-Compass produces. You do not need to know Kubernetes or GPUs to
follow it. Read the five ideas first, then go to the table you have in front of you.

## The five ideas behind every table

1. **Native, and native with Omni-Compass on top.** Omni-Compass never runs a machine by itself. Every result compares
   a system running alone ("native": Kubernetes alone, the card's own firmware alone, a building's own controller
   alone) with the same system with Omni-Compass sitting on top of it. Same machine, same work, same moment: the only
   difference is Omni-Compass.
2. **Paired runs.** Each comparison is run many times ("repetitions" or "runs"), each time with both arms on the same
   seed (the same pattern of work). Each repetition gives one difference; the table reports the average difference.
3. **The 95% interval.** Next to each average is a range, for example `+0.092% (+0.090 to +0.093)`. It means: if we
   ran this again and again, the true answer would land inside that range 95 times out of 100.
   - If the whole range is on one side of zero, the difference is **proven** (the table says "yes" or "significant").
   - If the range crosses zero, the difference is **not proven**: it could be noise.
4. **Better is not always "up".** For energy, response time, failures, machines and time over the line, **lower is
   better**, so a minus sign is good. For work per energy and work done, **higher is better**, so a plus sign is good.
   Every table says which.
5. **Evidence class.** Every result is marked with how it was measured:
   - **T**: a theorem;
   - **V**: verified in code;
   - **S**: a model (simulation);
   - **L**: live software (real Kubernetes);
   - **P**: a physical meter (a real card's own power meter).

   Only **P** speaks for hardware energy.

## The words in the tables

| Word | What it means | Better is |
|---|---|---|
| Work per energy | work done for each unit of energy (requests per kilojoule on a card) | higher |
| Energy (J, Wh) | the energy used | lower |
| Work, requests served | how much was done; both arms must serve the same work | equal |
| Response time, median (p50) | half of the answers were faster than this | lower |
| Response time, p95 | 95 of 100 answers were faster than this: the slow answers, what service promises are written on | lower |
| Response time, p99 | 99 of 100 answers were faster than this: the slowest answers | lower |
| Time over the line, violations (pp) | the share of time the service was past its promise, in percentage points | lower |
| Failed requests, not served | answers that never came | zero |
| Machines in service, node-hours | how many machines were kept on, and for how long | lower |
| Band first | the founder's rule: no win unless time over the line is no higher than native's | "held" |
| Knobs handed back, restored | at the end every setting Omni-Compass touched was put back exactly | True / yes |
| Label | the verdict, chosen by a rule written before the run, never by hand | see each table |

## The GPU card (`results/gpu/run-<stamp>/GPU_REPS.md`)

One card, three arms, many repetitions:
- **native**: the card's firmware alone;
- **watch**: Omni-Compass running and deciding but writing nothing. It must equal native: this proves Omni-Compass
  watching costs nothing;
- **omni**: Omni-Compass on top, moving the card's clock ceiling and power limit.

Read it in this order:
1. **The verdict line** at the top, one of: *better, proven*; *worse, proven*; *not proven*; *better on energy, fails
   the service guardrail*.
2. **Work per energy** (requests per kilojoule): the headline. A plus sign with a range wholly above zero is a proven
   gain.
3. **Requests served** must be equal in every arm. More energy saved by serving less work would be cheating; the bench
   checks it.
4. **p95 and p99**: the slow answers. With the verdict rule (`omnicompass/verdict.py`), Omni-Compass never takes a step
   that makes a request more than 2% slower.
5. **Writes and restore**: how many settings were changed, and that every arm ended at the card's own limit.

The file `omni-gpu-<stamp>-confirmations.tar.gz` holds two such tables: compute-bound work (matrix products) and AI
token generation (memory-bound work).

## The card inside the six organisms (`results/hil/run-<stamp>/HIL.md`)

The real card is wired into each of the six organisms (the four realms, the four stacked, the whole tower) at four
sizes (1, 10, 100 and 1,000 copies). Each row is one size, one organism and one part:
- **stacks (model)**: the simulated machines (evidence S);
- **card (meter)**: the real card, its own meter (evidence P);
- **both**: the two added together.

The second table lists the card's own receipts for every arm: its energy, requests served, p95, and its power limit at
the start and at the end, which must be equal.

## Real Kubernetes (`results/live/LIVE_REPS_<n>.md`)

Each set is 10 paired repetitions on a real Kubernetes cluster (kind): native Kubernetes (its HPA and scheduler)
against the same Kubernetes with Omni-Compass on top. Read:
1. **worker nodes in service** and **node-hours**: how many machines were kept busy. Minus is better.
2. **response time p95 and p99**: minus is faster.
3. **failed requests**: must be zero on both sides.
4. **CPU used with Omni's own**: Omni-Compass's own cost included; "no" in the significant column means it costs
   nothing measurable overall.
5. **The label** at the bottom, by the rule written before the run.

Energy on kind is a declared model, not a meter: kind keeps every machine powered.

## The six organisms grid (`results/scale/GRID.md`)

Columns are **size × runs**: 1, 10, 100 and 1,000 clusters, each at 1, 10, 100 and 1,000 paired runs. Rows are the six
organisms. There is one table each for work per energy, energy, time over the line and work done. Read a cell as
"with Omni-Compass on top, against native, at this size, over this many runs". Cells that are still computing say so;
1,000 runs at 1,000 clusters is beyond the machines available and says so.

## Kubernetes at scale (`KWOK.md`, from the `kwok-scale` workflow)

Real Kubernetes at 50, 500 and 1,000 nodes (KWOK nodes: real Kubernetes objects with no machines behind them):
- **decision time** is how long Omni-Compass takes to decide, at that size;
- **memory** is what it uses;
- **master switch** must read "yes": everything handed back.

## Where to start

1. `STATE_OF_PLAY.md`: one page, every result and how strong it is.
2. `docs/DOSSIER.md`: every result with its chart.
3. This chapter, next to the table in front of you.
4. `DISCLOSURES.md`: what a result is and is not.
