# Realm harness preregistration

Written and committed before the confirmation seeds were run. Evidence class **S**: every number the run produces
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
