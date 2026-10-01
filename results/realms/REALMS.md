# The realms: 656 muscles on modelled plants, native against Omni on top

Evidence class **S** (simulation). Run 2026-10-01 21:46 UTC, commit `76c7b2fee2f4`, seeds 1000-1009 (10 paired seeds per muscle and per organism). Preregistered in `docs/REALMS_PREREGISTRATION.md`; harness `realms/`; every plant and its native controller in `realms/plants.py`, every number in `realms/presets.py`. The governor is the frozen `omnicompass.adapter.Governor`, unchanged.

Primary outcome: work per energy, Omni against native, with its 95% interval over seeds. Guardrails: work not lower by more than 1%, share of periods in violation not higher by more than 1 percentage point. Labels by rule.

These are models. A model's energy is not a meter's, and a plant written by the same people who wrote the governor is not an independent test. What a row here can show is whether the governor's law, applied to that knob, helps or hurts the model, and where it breaks.

## The five organisms

| Organism | Muscles | Label | Work per energy | Work | Energy | Violations (pp) | Valid |
|---|---:|---|---:|---:|---:|---:|---|
| Compute / AI / Cloud | 250 | **WORSE** | -2.6% (-3.2 to -2.1) | -0.0% (-0.1 to -0.0) | +2.7% (+2.1 to +3.2) | +0.2 (+0.1 to +0.3) | yes |
| Physics / Robotics / Autonomous | 88 | **WORSE** | -2.6% (-3.0 to -2.2) | -0.0% (-0.0 to +0.0) | +2.7% (+2.2 to +3.1) | +1.8 (+1.7 to +2.0) | yes |
| Energy / Facility / Industrial | 121 | **WORSE** | -1.2% (-1.4 to -0.9) | -1.9% (-2.2 to -1.7) | -0.7% (-0.8 to -0.7) | +2.2 (+2.0 to +2.5) | yes |
| Distribution / Specialized | 197 | **WORSE** | -5.4% (-6.3 to -4.6) | +0.0% (-0.0 to +0.0) | +5.7% (+4.8 to +6.7) | -0.3 (-0.4 to -0.2) | yes |
| The whole tower (656 muscles) | 656 | **WORSE** | -0.1% (-0.1 to -0.1) | -0.3% (-0.4 to -0.3) | -0.2% (-0.3 to -0.2) | +0.3 (+0.3 to +0.4) | yes |

## Every muscle alone, by realm

| Realm | Muscles | SUPERIOR WITHIN GUARDRAILS | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | NONINFERIOR / INCONCLUSIVE | NOT ESTABLISHED | WORSE | INVALID |
|---|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud | 250 | 43 | 11 | 71 | 4 | 121 | 0 |
| Physics / Robotics / Autonomous | 88 | 22 | 7 | 47 | 9 | 3 | 0 |
| Energy / Facility / Industrial | 121 | 24 | 0 | 75 | 4 | 18 | 0 |
| Distribution / Specialized | 197 | 12 | 11 | 79 | 5 | 90 | 0 |
| **All** | 656 | **101** | **29** | **272** | **22** | **232** | **0** |

## By knob: what kind of authority Omni held

| Knob | Muscles | SUPERIOR WITHIN GUARDRAILS | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | NONINFERIOR / INCONCLUSIVE | NOT ESTABLISHED | WORSE | INVALID | Median work per energy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| capacity | 344 | 60 | 2 | 36 | 18 | 228 | 0 | -10.9% |
| setpoint | 55 | 26 | 20 | 6 | 3 | 0 | 0 | +3.3% |
| power | 63 | 15 | 7 | 36 | 1 | 4 | 0 | +0.0% |
| admission | 194 | 0 | 0 | 194 | 0 | 0 | 0 | +0.0% |

## Setpoint muscles: Omni against simply fixing the setpoint at the band's calm end

For 55 of 55 setpoint muscles, a fixed setpoint at the calm end of the declared band gave more work per energy than Omni moving it. On those muscles the gain is the band, not the governor. The fixed setpoint's own label (with its service guardrails) is in `MUSCLES.csv`.

## By family

| Realm | Family | Plant | Muscles | Superior | Tradeoff | Inconclusive | Not established | Worse | Invalid | Median work per energy |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud | AI Inference Serving | compute_pool (gpu) | 16 | 1 | 1 | 6 | 0 | 8 | 0 | +0.0% |
| Compute / AI / Cloud | AI Training | compute_pool (gpu_batch) | 16 | 15 | 0 | 1 | 0 | 0 | 0 | +6.6% |
| Compute / AI / Cloud | Cloud VM & Capacity | compute_pool (node) | 16 | 0 | 0 | 0 | 1 | 15 | 0 | -15.7% |
| Compute / AI / Cloud | Container Resources | compute_pool (server) | 16 | 0 | 2 | 1 | 0 | 13 | 0 | -11.4% |
| Compute / AI / Cloud | Cross-Cluster, Multi-Region & Edge | compute_pool (node) | 15 | 0 | 0 | 6 | 0 | 9 | 0 | -11.3% |
| Compute / AI / Cloud | DPU SmartNIC & Programmable IO | compute_pool (fabric) | 12 | 0 | 0 | 2 | 0 | 10 | 0 | -12.1% |
| Compute / AI / Cloud | Distributed Cluster Managers | compute_pool (batch) | 15 | 8 | 0 | 7 | 0 | 0 | 0 | +6.5% |
| Compute / AI / Cloud | GPU Fabric & RDMA | compute_pool (fabric) | 16 | 0 | 0 | 4 | 0 | 12 | 0 | -14.4% |
| Compute / AI / Cloud | HPC & Distributed Compute | compute_pool (batch) | 16 | 9 | 0 | 7 | 0 | 0 | 0 | +8.0% |
| Compute / AI / Cloud | Host CPU & Memory | compute_pool (cpu_host) | 16 | 8 | 0 | 1 | 0 | 7 | 0 | +2.7% |
| Compute / AI / Cloud | Kubernetes Dynamic Device Allocation | compute_pool (gpu) | 8 | 0 | 1 | 1 | 1 | 5 | 0 | -5.5% |
| Compute / AI / Cloud | Kubernetes Placement & Scheduling | compute_pool (server) | 16 | 0 | 1 | 4 | 0 | 11 | 0 | -11.1% |
| Compute / AI / Cloud | Kubernetes Workload Scaling | compute_pool (server) | 16 | 0 | 3 | 6 | 0 | 7 | 0 | +0.0% |
| Compute / AI / Cloud | NVIDIA GPU Hardware | compute_pool (gpu) | 15 | 2 | 2 | 2 | 1 | 8 | 0 | -6.4% |
| Compute / AI / Cloud | Node Fleet & Karpenter-Class Control | compute_pool (node) | 16 | 0 | 1 | 3 | 1 | 11 | 0 | -12.0% |
| Compute / AI / Cloud | OpenShift & Machine API | compute_pool (node) | 9 | 0 | 0 | 4 | 0 | 5 | 0 | -10.3% |
| Compute / AI / Cloud | Work Admission & Demand Shaping | compute_pool (server) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Cache & Memory Services | compute_pool (server) | 15 | 0 | 1 | 4 | 0 | 10 | 0 | -13.7% |
| Distribution / Specialized | Commerce & Payment Systems | compute_pool (commerce) | 15 | 0 | 2 | 8 | 0 | 5 | 0 | +0.0% |
| Distribution / Specialized | Data Analytics & ETL | compute_pool (batch) | 15 | 11 | 0 | 4 | 0 | 0 | 0 | +8.2% |
| Distribution / Specialized | Database & Transactions | compute_pool (database) | 14 | 0 | 0 | 5 | 0 | 9 | 0 | -10.3% |
| Distribution / Specialized | Messaging & Streaming | compute_pool (server) | 16 | 0 | 0 | 7 | 1 | 8 | 0 | -8.8% |
| Distribution / Specialized | Network Routing & Switching | compute_pool (network) | 16 | 0 | 3 | 6 | 0 | 7 | 0 | +0.0% |
| Distribution / Specialized | Observability & Telemetry | compute_pool (server) | 6 | 0 | 1 | 3 | 0 | 2 | 0 | +0.0% |
| Distribution / Specialized | Reliability, Security & Recovery | compute_pool (server) | 12 | 0 | 0 | 6 | 0 | 6 | 0 | +0.0% |
| Distribution / Specialized | Runtime & Application | compute_pool (server) | 15 | 0 | 0 | 5 | 1 | 9 | 0 | -11.7% |
| Distribution / Specialized | Search, Indexing & Vector DB | compute_pool (server) | 15 | 0 | 0 | 5 | 0 | 10 | 0 | -12.5% |
| Distribution / Specialized | Service Mesh & API Reliability | compute_pool (server) | 15 | 0 | 2 | 7 | 0 | 6 | 0 | +0.0% |
| Distribution / Specialized | Storage Block/File/Object | compute_pool (storage) | 16 | 0 | 0 | 2 | 0 | 14 | 0 | -27.2% |
| Distribution / Specialized | Telecom RAN & Edge Radio | compute_pool (ran) | 12 | 0 | 2 | 3 | 3 | 4 | 0 | -0.2% |
| Distribution / Specialized | Workflow, Logistics & Fulfillment | compute_pool (workflow) | 15 | 1 | 0 | 14 | 0 | 0 | 0 | +0.0% |
| Energy / Facility / Industrial | Building & Critical Environment HVAC | thermal_zone (building) | 12 | 0 | 0 | 8 | 3 | 1 | 0 | +0.0% |
| Energy / Facility / Industrial | Cooling, Chillers & Thermodynamics | thermal_zone (data_hall) | 15 | 6 | 0 | 2 | 1 | 6 | 0 | +0.0% |
| Energy / Facility / Industrial | Energy Storage & Microgrid | energy_storage (microgrid) | 16 | 2 | 0 | 12 | 0 | 2 | 0 | -0.0% |
| Energy / Facility / Industrial | Facility & Grid Optimization | energy_storage (facility) | 15 | 0 | 0 | 10 | 0 | 5 | 0 | -0.0% |
| Energy / Facility / Industrial | Grid Transmission & Distribution | process_loop (feeder_voltage) | 12 | 4 | 0 | 8 | 0 | 0 | 0 | +0.0% |
| Energy / Facility / Industrial | Industrial PLC & Process Automation | process_loop (process) | 14 | 6 | 0 | 8 | 0 | 0 | 0 | +0.0% |
| Energy / Facility / Industrial | PDU, UPS & Electrical Distribution | energy_storage (ups) | 14 | 0 | 0 | 10 | 0 | 4 | 0 | +0.0% |
| Energy / Facility / Industrial | Semiconductor Fab & Precision Manufacturing | process_loop (chamber) | 11 | 2 | 0 | 9 | 0 | 0 | 0 | +0.0% |
| Energy / Facility / Industrial | Water Wastewater & Pumping | process_loop (water) | 12 | 4 | 0 | 8 | 0 | 0 | 0 | +0.0% |
| Physics / Robotics / Autonomous | Automotive EV & Mobile Powertrain | motion_axis (ev_traction) | 12 | 0 | 0 | 11 | 1 | 0 | 0 | +0.0% |
| Physics / Robotics / Autonomous | Aviation & Autonomous Flight | motion_axis (flight_axis) | 16 | 7 | 0 | 9 | 0 | 0 | 0 | +0.0% |
| Physics / Robotics / Autonomous | Quantum Computing Control Simulation | compute_pool (qpu) | 16 | 0 | 3 | 4 | 8 | 1 | 0 | +0.4% |
| Physics / Robotics / Autonomous | Robotics Fleet & Warehouse Automation | compute_pool (robot_fleet) | 15 | 0 | 0 | 13 | 0 | 2 | 0 | -0.3% |
| Physics / Robotics / Autonomous | Robotics Motion Control | motion_axis (robot_joint) | 15 | 11 | 0 | 4 | 0 | 0 | 0 | +0.3% |
| Physics / Robotics / Autonomous | Spacecraft & Flight Software | motion_axis (reaction_wheel) | 14 | 4 | 4 | 6 | 0 | 0 | 0 | +2.1% |

## Largest gains and largest losses (single muscles, by mean work per energy)

| Muscle | Family | Knob | Label | Work per energy | Work | Violations (pp) |
|---|---|---|---|---:|---:|---:|
| pressure_setpoint | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +33.5% (+31.5 to +35.4) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| tank_level_target | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +32.7% (+30.3 to +35.1) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| valve_position | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +32.6% (+30.6 to +34.7) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| furnace_setpoint | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +32.6% (+30.5 to +34.7) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| mass_flow_setpoint | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +32.5% (+30.1 to +34.9) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| temperature_setpoint | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +32.2% (+30.2 to +34.1) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| pulse_duration | Quantum Computing Control Simulation | setpoint | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | +13.1% (+12.0 to +14.3) | -0.0% (-0.0 to +0.0) | +0.6 (-0.1 to +1.4) |
| reservoir_level_target | Water Wastewater & Pumping | setpoint | SUPERIOR WITHIN GUARDRAILS | +12.9% (+11.8 to +14.1) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| valve_position_water | Water Wastewater & Pumping | setpoint | SUPERIOR WITHIN GUARDRAILS | +12.9% (+11.8 to +13.9) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| line_pressure_target | Water Wastewater & Pumping | setpoint | SUPERIOR WITHIN GUARDRAILS | +12.6% (+11.4 to +13.8) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| bandwidth_limit | Network Routing & Switching | capacity | WORSE | -38.3% (-50.2 to -26.4) | +0.0% (-0.0 to +0.0) | -0.1 (-0.4 to +0.3) |
| object_replication | Storage Block/File/Object | capacity | WORSE | -36.2% (-46.8 to -25.6) | +0.0% (-0.0 to +0.0) | +0.1 (-0.4 to +0.7) |
| throughput_limit | Storage Block/File/Object | capacity | WORSE | -33.9% (-41.4 to -26.5) | -0.0% (-0.0 to +0.0) | -0.1 (-0.8 to +0.5) |
| snapshot_trigger | Storage Block/File/Object | capacity | WORSE | -33.9% (-41.6 to -26.2) | +0.0% (-0.0 to +0.0) | +0.4 (-0.0 to +0.9) |
| building_demand_limit | Building & Critical Environment HVAC | power | WORSE | -32.6% (-55.1 to -10.2) | -35.2% (-59.0 to -11.3) | +25.3 (+8.3 to +42.3) |
| backfill_rate | Storage Block/File/Object | capacity | WORSE | -31.7% (-41.8 to -21.5) | +0.0% (-0.0 to +0.0) | +0.6 (+0.2 to +0.9) |
| erasure_code_profile | Storage Block/File/Object | capacity | WORSE | -30.6% (-42.1 to -19.0) | +0.0% (-0.0 to +0.0) | +0.3 (-0.1 to +0.8) |
| rebalance | Storage Block/File/Object | capacity | WORSE | -30.2% (-41.7 to -18.8) | +0.0% (-0.0 to +0.0) | +0.2 (-0.2 to +0.5) |
| recovery_rate | Storage Block/File/Object | capacity | WORSE | -29.8% (-44.0 to -15.6) | -0.0% (-0.0 to +0.0) | +0.3 (-0.4 to +0.9) |
| iops_limit | Storage Block/File/Object | capacity | WORSE | -28.9% (-39.0 to -18.8) | -0.0% (-0.0 to +0.0) | +0.3 (-0.1 to +0.8) |

## Validity

- Watch equal to native and the kill switch handing back the knob: 656 of 656 muscles; 5 of 5 organisms.
- Raw per-seed contrasts: `REALMS.json`. One row per muscle: `MUSCLES.csv`. Fingerprints: `RUN.json`, `SHA256SUMS.txt`.
