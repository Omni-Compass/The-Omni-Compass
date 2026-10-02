# Realm study, wave 3: the 656 checked against the real systems

Waves 1 and 2 listed the real controls of each realm from the systems' own documentation (Kubernetes, Linux, NVIDIA, the clouds, ROS 2, PX4, BACnet, IEEE 1547 / 2030.5, IEC 61850, SEMI, PostgreSQL, Kafka, Redis, Envoy, O-RAN and others) and from what Meta, Google, Microsoft, Intel, NVIDIA, Netflix and Uber publish about production. Wave 3 checks every catalog row against them (`wave3_map.csv`, hand verdicts in `wave3_verdicts.csv` and `wave3_overrides.csv`).

## The 656, row by row

| Verdict | Rows | Meaning |
|---|---:|---|
| real | 578 | a real control, named with its setting and source |
| real, application level | 7 | real, but set in the application rather than a platform |
| real, configuration only | 1 | real, but configured once, not moved at run time |
| real, missing from waves 1-2 | 15 | real; added to the list of controls |
| duplicate | 45 | the same control as another catalog row |
| protective | 4 | a safety action owned by a safety system; never for an optimiser |
| not a control | 6 | moves no setting (an objective, an alert, or not settable) |

After folding duplicates (including rows that point at the same real control), **448** catalog rows are distinct real controls. Some of that folding is by mechanism, not by loop: the furnace, pressure, temperature and level setpoints all fold into one "PID setpoint" control. On a real plant each loop is its own muscle, so 448 is a floor for distinct controls, not a ceiling.

## Real controls the 656 does not have

**124** real controls from waves 1 and 2 are not in the catalog, among them the HPA's own behaviour settings (stabilisation windows, rate policies, tolerance), the Cluster Autoscaler's scale-down settings, CPU governor and turbo, NVIDIA application clocks and sync boost, IEEE 1547 volt-var and volt-watt, Guideline 36 trim-and-respond, PostgreSQL and InnoDB resource settings, and the production power-capping practices (hierarchical budgets, priority-aware capping, core packing). They are added.

## The true muscle list, by realm

| Realm | From the 656 | Added | True total |
|---|---:|---:|---:|
| Shared spine (all four realms) | 135 | 70 | **205** |
| Compute / AI / Cloud | 94 | 20 | **114** |
| Physics / Robotics / Autonomous | 60 | 9 | **69** |
| Energy / Facility / Industrial | 65 | 12 | **77** |
| Distribution / Specialized | 94 | 13 | **107** |
| **All** | **448** | **124** | **572** |

Each realm's organism is its own row plus the shared spine. Every row of `TRUE_MUSCLES.csv` names the real control, its system, its exact setting and its source; `SET_ASIDE.csv` lists every catalog row not kept, with the reason.

## What this does not claim

- **This is not every setting that exists.** Linux alone has thousands. The list is the controls that change a system's energy, capacity or service and that a supervisory governor could hold, as the systems document them.
- **The verdicts are hand judgements on documented controls**, made row by row and each one written down, so any of them can be contested.
- **The realm harness still runs on the 656 catalog (round 3).** Moving it onto this list is a new round, with its own preregistration.
