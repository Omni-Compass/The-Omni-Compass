# Realm harness preregistration

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Round 3 is the current one: its section at the end changes only how the realms are made up. Round 2's section
replaced round 1's Omni layer. Round 1 below is kept as it
was frozen. Each round was written and committed before its confirmation seeds were run. Evidence class **S**: every number the run produces
comes from a declared model. Nothing here is a meter, and nothing here is evidence about a real machine.

## Question

For each of the 656 muscles of the canonical tower, and for each realm and the whole tower run as one organism: does
the frozen governor (`omnicompass.adapter.Governor`, the engine with u = 0, the stack law, the kill switch), holding
that muscle's one knob on top of the plant's native controller, change work per energy against the native controller
alone, without buying it with service?

## What runs

- **The catalog** (`realms/catalog.csv`, built by `tools/realms_catalog.py`): the 656 rows of the XPASS package's
  canonical tower, unchanged, plus four columns given by fixed rules: realm, plant, parameter set, knob.
  - Compute / AI / Cloud: 250 muscles. Physics / Robotics / Autonomous: 88. Energy / Facility / Industrial: 121.
    Distribution / Specialized: 197.
- **Five plants** (`realms/plants.py`), each with its own native controller, all parameters in `realms/presets.py`:
  - compute_pool: request stream, servers with start-up delay, idle and dynamic power; native: the HPA rule
    (10% tolerance, scale-down stabilisation window), fixed admission limit, full clock;
  - thermal_zone: zone heat balance, staged cooling units, COP from supply and outdoor temperature; native: PI on a
    fixed setpoint, units staged to the load;
  - energy_storage: site load, solar, battery, grid connection with a contract limit; native: self-consumption above
    a fixed reserve;
  - motion_axis: point-to-point moves from a task queue, motor copper losses and heating, derating; native: PID with
    feedforward at full speed;
  - process_loop: first-order process with dead time, pump or heater power; native: PI on a fixed setpoint.
- **A muscle is one knob of one plant.** Omni holds only that knob: capacity (the adapter's capacity law for one
  plant), setpoint (inside a declared band: calm end at rho0, stress end at rho_min), power (the directive's power
  cap), or admission (native while change is permitted; while not, only what clears inside the service target, or
  the flexible share deferred or shed).
- **Each muscle's plant is sized** by a factor 0.6 to 1.4 drawn from its muscle id.

## Arms

On the same seed, so with the same demand, weather and disturbances:

- **native**: the plant and its native controller;
- **watch**: the governor reads every period and writes nothing;
- **omni**: the governor holds the knob; at 90% of the run it is killed and the knob returns to the native controller;
- **fixed_calm** (setpoint muscles only, descriptive): the native controller with the setpoint fixed at the band's
  calm end. It shows how much of a setpoint result the band alone gives.

Organisms: every plant of a realm (or all 656) on one 15 s clock for one hour. Plants are coupled:
- the electrical power of compute, motion and process plants is heat in the realm's thermal zones;
- the organism's load swing is load on its storage sites;
- the zones' temperature is the ambient every other plant reports.

One governor reads the organism's aggregate, and its one directive sets every muscle's knob.

## Seeds and repetitions

Confirmation seeds 1000 to 1009: ten paired seeds per muscle and per organism. Development used seeds 0 and 1 only.
Nothing from development seeds is reported.

## Outcomes

- **Primary**, per seed: (work_omni / work_native) / (energy_omni / energy_native) − 1. Work is in the plant's own
  units: requests, IT heat held in specification, site load served, moves completed, or product delivered in
  specification. For an organism, work is the mean over its plants of work_omni / work_native, and energy is total
  joules.
- **Guardrails**, both must hold:
  - work: the 95% interval of work_omni / work_native − 1 must not reach below −1%;
  - violations: the 95% interval of the change in the share of periods in violation must not reach above +1
    percentage point.

  Violation, per plant:
  - compute: response time over the service target, or a dropped request;
  - thermal: zone over its limit;
  - storage: grid import over the contract limit;
  - motion: tracking error over its bound, winding over temperature, or the oldest task waiting past its deadline;
  - process: the process variable outside its specification.
- **Label, by rule** (`realms/harness.py`, `label()`, the GPU bench's rule):
  - SUPERIOR WITHIN GUARDRAILS;
  - ENERGY IMPROVEMENT WITH SERVICE TRADEOFF;
  - NONINFERIOR / INCONCLUSIVE;
  - NOT ESTABLISHED;
  - WORSE;
  - INVALID.

## Invalid

A muscle or organism is labelled INVALID if, on any seed:
- the watch arm differs from native in any meter or writes anything;
- the omni arm writes after the kill;
- a knob is not back at its native value after the kill;
- any contrast is not finite.

## Recorded

Per muscle and organism:
- every per-seed contrast;
- writes per run;
- the native violation share;
- the fixed-setpoint comparison where it applies.

Per run: the commit, the seeds, and the fingerprints of the catalog, the engine, the governor and the whole frozen
tree (`RUN.json`, `SHA256SUMS.txt`). The confirmation refuses to run on uncommitted code.

## Changes made on the development seeds, before this freeze

The development runs found bugs and sizing faults. Each was fixed before the confirmation seeds were run:

- **The admission knob was inverted**: it admitted only what cleared the service target while change was permitted.
  Fixed to the declared rule.
- **The compute admission limit compared the queue limit with the period's arrivals** instead of the backlog left
  after the period's service. Fixed for native and Omni alike.
- **The capacity law did not clip the queue and load readings to [0, 2]**, as the adapter's `observe_vector` does.
  Fixed.
- **Thermal and process utilisation was measured against the uncapped capacity** while the power cap was held, so the
  power law's trim ratcheted to its floor. Fixed: utilisation of the capacity actually available.
- **Compute plants reported a heat proxy of my own.** Replaced by the live controller's own thermal model
  (`omni_controller/muscles.py`).
- **Thermal zones kept fixed cooling units while their IT load was scaled.** The large halls were under-provisioned,
  so the native controller overheated. Cooling now scales with the hall.
- **The flight axis's motor thermal resistance was ten times too high**, so the native controller was always derated.
  Corrected. The UPS feed was sized under its own load; sized at 1.2 times.
- **The slow plants** (vehicle, spacecraft, flight) completed too few tasks in six minutes to measure. They now decide
  every 5, 10 and 2 seconds over the same 360 decisions.
- **Added the fixed_calm arm** for setpoint muscles, after development showed that the band's calm end alone accounts
  for much of the setpoint results.

None of these changes was chosen by its effect on Omni's result. The development runs showed losses as well as gains
for Omni before and after them.

## Not claimed

- **No row is evidence about a real machine.** A row says what the governor's law does to that model through that
  knob.
- **The plants, native controllers and bands were written by the same project as the governor.** That is a real
  conflict, so every one of them is in two files, to be read and contested.
- **A muscle's name chooses its knob and its plant's size; it does not get its own physics.** The 16 muscles of a
  family share the family's plant model at different sizes, through different knobs.
- **The plant code is Python only.** The governor's C++ twin is unchanged; a C++ twin of the plants is open.

## Round 2 (2026-10-01, after round 1's results; before any round-2 confirmation seed)

Round 1 (seeds 1000-1009) labelled all five organisms WORSE. Reading the result against the shipped controller
(`omni_controller/controller.py`, `omni_controller/muscles.py`, `omnicompass/nervous_system.py`) showed that round 1's
Omni layer was not the Omni that runs on Kubernetes. Round 1 is kept unchanged in `results/realms/round1/`, with a note
saying why it is superseded. Round 2 changes only how Omni commands a knob, the native machine-pool scaler and the
declared budgets. These changes were made after seeing round 1, so they are listed with the source line each one follows:

| Round 1 | Round 2, as the shipped controller does it |
|---|---|
| Capacity muscles replaced the HPA with the stack simulator's capacity law (release one unit after convergence, dwell and a 20% band) | Pods: the HPA target written as min(rho*, the operator's target), never tighter, held one autoscaler window; the HPA scales (`controller.py`, HPA target patch). Machine pools: the node release gate, one machine per decision (`nervous_system.node_release_gate`) |
| HPA-type setpoints moved inside a band whose calm end was tighter than the operator's target | The same min(rho*, operator) rule: more headroom is always allowed, less never (`controller.py`) |
| No contraction authority and no SLO reflex | Every contraction needs the organ's authority (calm >= threshold, senses live) and three clean decisions; while service is breached the knob returns to native (`nervous_system.authority`, `muscles.py` SLO reflex) |
| Continuous knobs jumped to the governed value | Down by at most the calm share of the surplus per decision (`nervous_system`: step = calm) |
| Request-served pools had their power capped | Never: throttling request work saves no energy and adds wait (`muscles.py`, `_power_cap`); GPU and CPU-frequency pools use their envelope, never under draw x 1.3 |
| Thermal setpoint by headroom | The live cooling law: warm while cool, cold as heat rises, under the envelope 18 + 9 x calm mapped onto the band (`muscles.py`, `_cooling`) |
| Admission paused every admission muscle, request traffic included, and resumed only when fully calm | Batch pacing of pausable work only: one muscle suspended per decision at power stress >= 0.95 or heat >= 0.96 (or a nervous pause), one resumed per decision at power stress <= 0.8 and heat < 0.90 (`muscles.py`, `_batch_pace` defaults); request traffic never paused |
| queue_ratio was the backlog in service-target units | pending starts per serving unit, or latency pressure (p95 / target − 1, or the failed share), capped at 2 (`controller.py`) |
| The governor's current cap followed the applied cap | 1.0, as the live controller sets it |
| Site power budget 1.25 x a formula nominal that sat under the organism's real native draw (compute ran at 1.2 x it), so the governor read the site as always at its limit | 1.25 x each plant's mean native draw on the calibration seed 999 (never a result seed); compute pools alone likewise |
| Organism heat = the hottest of up to 656 plants | The mean, as every other organism channel; local heat stays with each plant's own reflex |
| Native machine pools used the HPA rule | The Cluster Autoscaler's defaults: add while work waits, remove one machine after the rest has been under 50% for 10 minutes |
| Building cooling sized under its own peak (native overheated half the time) | Units of 35 kW: capacity 1.25 x the declared peak |

Unchanged: the plants' physics, the catalog, every other parameter, the arms, the outcomes, the guardrails, the
label rule and the invalidity rules.

- **Round 2 seeds:** 2000 to 2009. Development of round 2 used seeds 0 and 1 only, never reported.
- **Results:** `results/realms/` (round 1 in `results/realms/round1/`). Both rounds are cited together.

## Round 3 (2026-10-02, after round 2's results; before any round-3 confirmation seed)

Only the make-up of the realm organisms changes. The plants, the Omni layer, the outcomes, the guardrails, the label
rule and the invalidity rules are round 2's, unchanged.

- **Round 2 cut the 656 into four realms with no overlap.** No realm organism carried the infrastructure every real
  stack runs on unless that infrastructure was the realm's own. The data-centre realm had no cooling or power, and
  the robotics and plant realms had no Kubernetes, machines or GPUs.
- **Round 3 gives every realm the shared spine** (`tools/realms_catalog.py`, SPINE): Kubernetes Workload Scaling,
  Placement & Scheduling, Container Resources, Node Fleet, Cloud VM & Capacity, NVIDIA GPU Hardware, Host CPU &
  Memory, Network Routing, Storage, Observability, Reliability & Security, Cooling & Chillers, PDU / UPS &
  Electrical Distribution.
  - Each realm's organism is its own families plus the spine: Compute 345 muscles, Physics 262, Energy 282,
    Distribution 337.
  - The whole-tower organism still holds each of the 656 once.
- **Quantum Computing Control moves to the compute realm** (it behaves as a compute job queue).
- **Round 3 seeds:** 3000 to 3009. Round 2 is kept in `results/realms/round2/` with a note on why it is superseded.

## Round 4: the stacked organism (2026-10-02, before any round-4 seed)

The four realm organisms of round 3, stacked on one 15 s clock (`realms/harness.py`, `run_stack`; `tools/run_stack.py`).
Every muscle appears as often as it appears in the realms, duplicates included: 345 + 262 + 282 + 337 = 1,226. A
duplicate is still a muscle that has to converge. Each realm keeps its own internal coupling. The plants, the Omni
layer, the outcomes, the guardrails and the label rule are round 3's.

- **Arms:** native (no governor); separate (one governor per realm); one (one governor over the whole stack, reading
  the mean of all 1,226 muscles and the stack's total power against its total budget).
- **Check, required for validity:** the stacked native run equals each realm's own native run, plant by plant, on
  every seed. Stacking must change nothing natively.
- **Comparisons, each labelled by the rule:**
  - one governor against native;
  - separate governors against native;
  - one governor against separate governors (does one Omni over everything beat four).
- **Seeds:** 4000 to 4009. Development used seed 0 only, never reported.

## Round 5: the whole stacks with the real card inside (written 2026-10-02, before any run)

One harness (`tools/run_hil.py`, started by `scripts/gpu_rented_run.sh` after a valid card smoke): each of the six
organisms (the four realms, the four stacked with every duplicate kept (1,226), the whole tower of 656) runs on one clock as in round 3, with the machine's real GPU wired
in as one more muscle of its NVIDIA GPU family (a spine family, so the card is in every organism). The card serves the
pinned request stream; its own power.draw is heat in the organism's thermal zones and load on its storage sites.

- **Arms:** native (the stacks' own controllers, the card's own firmware) and omni (one engine on everything: the bowl
  law on every simulated muscle, `realms/bowl_arm.py`, and on the card's two wires, `omni_controller/gpu_bowl.py`). At
  90% of each arm every knob and both wires are handed back; a knob not handed back, a card limit not back at its
  start, or a card governor exiting non-zero makes the run invalid (exit 2).
- **Seeds and repetitions:** 3 paired repetitions, seeds 6000-6002; arm order alternates by repetition and organism.
- **Clock:** 240 steps of 2 s of wall clock per arm (the card in real time).
- **Outcomes:** work per energy, work, energy and violations, Omni against native, for three parts kept apart: the
  simulated stacks (evidence S), the card (its own meter, evidence P), and both added (the card as one more plant,
  its joules added to the stacks'). Labels by the round 3 rule.

## Round 6: the compute pools inside the band (2026-10-03, before any round-6 seed)

Round 3's rule (band first) was not held on the organisms: the bowl law spent 0.20 to 0.29 points more time over the
service line than native in every completed cell of the grid (`results/scale/GRID.md`). The cause was measured on the
whole tower (seeds 7000-7003), muscle by muscle:
- **compute pools giving a machine back** (42 muscles): +1.77 points of their own time over the line;
- **the HPA target set looser than the operator's** (249 muscles): +0.22 points;
- the process and thermal setpoints, which save the most energy, added none.

Two changes, both in `realms/bowl_arm.py`, everything else as round 3:
1. **The HPA target is held at the operator's own.** Loosening it past native costs the service time. This is the same
   rule as the card's speed floor and the live controller's cover.
2. **A machine goes back only when the machines left cover the recent peak at 0.6 of the plant's own release level**
   (`RELEASE_MARGIN`). A machine boots in minutes, so a burst that arrives after a release is served late until the
   machine is back.

**How 0.6 was chosen** (10 paired seeds per organism; the rule is the most work per energy whose whole interval of time
over the line is at or under native): 1.0, 0.8, 0.75, 0.7, 0.65 and 0.6 on the tower; 0.65 and 0.6 on the other five.
- 0.65 failed on Physics, the upper end of its interval +0.001;
- 0.6 held on all six.

**Checked on 20 paired seeds (7000-7019), before this round's official seeds:**

| Organism | Work per energy | Time over the line | Work done |
|---|---|---|---|
| Compute | +0.095% | −0.017 pp | unchanged within its interval (−0.001% to +0.000%) |
| Physics | +0.086% | −0.011 pp | unchanged within its interval (−0.001% to +0.000%) |
| Energy | +0.201% | −0.031 pp | unchanged within its interval (−0.001% to +0.000%) |
| Distribution | +0.090% | −0.015 pp | unchanged within its interval (−0.001% to +0.000%) |
| The four stacked | +0.153% | −0.022 pp | unchanged within its interval (−0.001% to +0.000%) |
| The whole tower | +0.194% | −0.010 pp | unchanged within its interval (−0.001% to +0.000%) |

Every knob was handed back. The grid runs at 100× and 1,000× now on GitHub were started on round 3's law. They are
recorded as round 3's result, and the grid is rerun on round 6's law.

## Round 5, amended (2026-10-03, before any round-5 run on the corrected law)

The whole stacks with the real card inside run at four sizes, as the six-organism grid does: each organism as 1, 10, 100
and 1,000 copies governed together on one clock, with the one real card inside as one more muscle of its NVIDIA GPU
family, native against Omni on top. Repetitions by size: 3, 3, 2 and 1 (seeds from 6000).

The step is 2 s of wall clock wherever the simulation keeps up. A size whose step takes longer gets a longer step:
1.5 times the measured time per muscle on that machine, times its muscles. The card's request stream runs for the same
240 steps, so the card and the stacks stay on one clock. The step of every size is in the receipt. At 1,000 copies the
card is one muscle among hundreds of thousands, so its watts are a small share of the organism's; that is the
arithmetic of one card in a large stack, and the card's own meter is reported apart from the stacks. Everything else is
as round 5. The two GPU confirmations now run before this stage, so the most important results are in hand first.

## Round 6 receipts and the one rule (2026-10-03)

At 1x and 10x (1,000 paired runs each) every organism is labelled superior within guardrails, with band first held and
every knob handed back (`results/scale/receipts/`, `results/scale/GRID.md`). At 1,000 runs the intervals are narrow
enough to show one cost: work done is lower by 0.0001% to 0.001%, wholly below zero in several organisms. Its cause was
measured on the Physics organism, muscle by muscle. It is the thermal zones: a room held warmer keeps a little less
margin, so a sudden heat spike puts it over its limit for a few extra seconds inside a step that already counts as
over the line.

Limiting how far a room may drift (half, a quarter, none of the way toward its warm end; 40 paired seeds) does not
remove it until the setpoint is held native, and then the Physics organism uses more energy than native. The cost is
therefore disclosed and judged by the one rule now written for every muscle (`DISCLOSURES.md`, section 3): at most 2% in
any measure, only where energy is saved. The largest work cost in the grid is 0.007% in a single run and 0.001% over
1,000 runs, far inside it.

### The 1,000-copy size: memory and sharding (2026-10-03, before its re-run)

The first 1,000-copy run (six run 37090435347) stopped twice at the same point: every organism larger than physics
and robotics ran out of memory about 3 minutes in (the four stacked at 1,000 copies is 1.2 million plants; at 33 KB a
plant, and with the calibration organism built while the result organism was still held, it needed over 40 GB on a
16 GB runner). Three changes, none of which changes a number:
- the calibration run is made before the organism, so one organism is in memory at a time (`realms/harness.py`, `Body`);
- each plant is packed as it is made: its exogenous series as machine arrays, its random source dropped (every plant
  draws its series when it is made, never while it runs), plants with the same parameters sharing one table
  (`realms/plants.py`, `pack`, `_shared`);
- the six workflow sizes its shards by organism (`per_shard`, `workers` by organism), because one run of the four
  stacked at 1,000 copies takes 2 to 3 hours and a runner's job ends at 6.

Same outputs: four organisms, two seeds each, at 1x to 3x, byte-identical before and after. A plant now takes 6.7 KB;
the four stacked at 1,000 copies needs about 9 GB. The re-run: 10 runs per organism at 1,000 copies (the 1-run and
10-run cells); 100 runs at 1,000 copies follows when the runners allow it (about 650 runner-hours).
