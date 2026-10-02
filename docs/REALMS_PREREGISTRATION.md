# Realm harness preregistration

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

One harness (`tools/run_hil.py`, started by `scripts/gpu_rented_run.sh` after a valid card smoke): each of the five
organisms (the four realms, the whole tower of 656) runs on one clock as in round 3, with the machine's real GPU wired
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
