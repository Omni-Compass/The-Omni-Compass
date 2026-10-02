# Speed-first pass: can Omni-Compass beat Kubernetes on every gauge in every scenario? (development seeds only)

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Plant: fleet/sim_slo.py (the frozen fleet plant plus a response-time gauge; the frozen omni_fleet trace is reproduced
exactly). Opponent: HPA 0.7 + Cluster Autoscaler. Scenarios: web, multi, batch, gpu x seeds 101-104. Rule: no gauge
worse in any scenario (0.5% tolerance; 0 on counts). 400 random configurations: 200 of the frozen law family with a
response-time nerve (tuning/SLO_SEARCH_FROZEN_LAW_11.json), 200 of the new speed law omnicompass/speed.py
(tuning/SPEED_SEARCH_21.json). Nothing here is held-out evidence.

## Result: no configuration passed. Three reasons, all measured

1. **The frozen fleet mode was never scored on response time.** Measured now: web p95 132 ms -> 20.3 s, p99
   3.1 s -> 76 s, batch p95 100 ms -> 6.3 s (energy -31%). Its constants were chosen for lowest energy with a
   rule that checked work done and backlog, not waiting time.
2. **Some gauges are already at their physical floor.** Work completed 100%, time healthy 100%, violations 0 on
   web/multi/batch; batch p95 = 100 ms = pure service time (no request waits). Tying is the best any controller
   can do there. On gpu, demand exceeds the 12-machine maximum: every arm is saturated (work 89%), nothing to win.
3. **Energy, response time and machine churn form a triangle: two of three.** The Cluster Autoscaler's idle
   slack (it keeps nodes until request use is under 50% for 10 minutes) is both where the energy is and what
   absorbs the 90-second boot delay. Examples (mean improvement vs Kubernetes, positive = better):
   - frozen fleet: energy +31%, response time far worse
   - speed law #176: energy +1.2%, p99 +41%, mean +17%, machine starts/stops 3.6x worse, reversals 6.7x worse
   - speed law #159: p99 +48%, mean +24%, starts/stops +27%, reversals +46%, energy -16%
   - same pods, tighter packing (grid): energy +3.5%, p99 -35%

## Next
Anticipation (the engine pre-adds machines before the diurnal rise instead of reacting) is the one mechanism that
could break the triangle; to be tested on these same development seeds, then frozen and held out.
