# The realms, round 2: 656 muscles on modelled plants, native against Omni on top

Evidence class **S** (simulation). Run 2026-10-01 22:26 UTC, commit `d801ec58fb29`, seeds 2000-2009 (10 paired seeds per muscle and per organism). Preregistered in `docs/REALMS_PREREGISTRATION.md` (round 2); round 1 is kept in `round1/`; harness `realms/`; every plant and its native controller in `realms/plants.py`, every number in `realms/presets.py`. The governor is the frozen `omnicompass.adapter.Governor`, unchanged, and every knob obeys the shipped nervous system (`omnicompass/nervous_system.py`) the way the live controller's organs do.

Primary outcome: work per energy, Omni against native, with its 95% interval over seeds. Guardrails: work not lower by more than 1%, share of periods in violation not higher by more than 1 percentage point. Labels by rule.

These are models. A model's energy is not a meter's, and a plant written by the same people who wrote the governor is not an independent test. What a row here can show is whether the governor's law, applied to that knob, helps or hurts the model, and where it breaks.

## The five organisms

| Organism | Muscles | Label | Work per energy | Work | Energy | Violations (pp) | Valid |
|---|---:|---|---:|---:|---:|---:|---|
| Compute / AI / Cloud | 250 | **ENERGY IMPROVEMENT WITH SERVICE TRADEOFF** | +2.5% (+2.3 to +2.7) | -0.2% (-0.2 to -0.2) | -2.6% (-2.8 to -2.4) | +2.9 (+2.7 to +3.0) | yes |
| Physics / Robotics / Autonomous | 88 | **WORSE** | -1.9% (-2.4 to -1.3) | -1.2% (-2.3 to -0.1) | +0.7% (-0.5 to +1.8) | +2.9 (+0.5 to +5.4) | yes |
| Energy / Facility / Industrial | 121 | **SUPERIOR WITHIN GUARDRAILS** | +0.3% (+0.3 to +0.3) | +0.0% (+0.0 to +0.0) | -0.3% (-0.3 to -0.3) | -0.1 (-0.1 to +0.0) | yes |
| Distribution / Specialized | 197 | **NONINFERIOR / INCONCLUSIVE** | +0.0% (+0.0 to +0.0) | +0.0% (+0.0 to +0.0) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) | yes |
| The whole tower (656 muscles) | 656 | **SUPERIOR WITHIN GUARDRAILS** | +0.1% (+0.1 to +0.1) | -0.1% (-0.1 to -0.0) | -0.2% (-0.2 to -0.2) | +0.7 (+0.5 to +0.8) | yes |

## Every muscle alone, by realm

| Realm | Muscles | SUPERIOR WITHIN GUARDRAILS | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | NONINFERIOR / INCONCLUSIVE | NOT ESTABLISHED | WORSE | INVALID |
|---|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud | 250 | 14 | 43 | 174 | 0 | 19 | 0 |
| Physics / Robotics / Autonomous | 88 | 16 | 10 | 47 | 5 | 10 | 0 |
| Energy / Facility / Industrial | 121 | 29 | 7 | 52 | 3 | 30 | 0 |
| Distribution / Specialized | 197 | 0 | 0 | 188 | 0 | 9 | 0 |
| **All** | 656 | **59** | **60** | **461** | **8** | **68** | **0** |

## By knob: what kind of authority Omni held

| Knob | Muscles | SUPERIOR WITHIN GUARDRAILS | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | NONINFERIOR / INCONCLUSIVE | NOT ESTABLISHED | WORSE | INVALID | Median work per energy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| capacity | 344 | 26 | 45 | 257 | 1 | 15 | 0 | +0.0% |
| setpoint | 55 | 19 | 1 | 21 | 0 | 14 | 0 | +0.0% |
| power | 63 | 14 | 4 | 42 | 0 | 3 | 0 | +0.0% |
| admission | 194 | 0 | 10 | 141 | 7 | 36 | 0 | +0.0% |

## Setpoint muscles: Omni against simply fixing the setpoint at the band's calm end

For 54 of 55 setpoint muscles, a fixed setpoint at the calm end of the declared band gave more work per energy than Omni moving it. On those muscles the gain is the band, not the governor. The fixed setpoint's own label (with its service guardrails) is in `MUSCLES.csv`.

## By family

| Realm | Family | Plant | Muscles | Superior | Tradeoff | Inconclusive | Not established | Worse | Invalid | Median work per energy |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Compute / AI / Cloud | AI Inference Serving | compute_pool (gpu) | 16 | 1 | 0 | 15 | 0 | 0 | 0 | +0.0% |
| Compute / AI / Cloud | AI Training | compute_pool (gpu_batch) | 16 | 1 | 0 | 12 | 0 | 3 | 0 | -0.0% |
| Compute / AI / Cloud | Cloud VM & Capacity | compute_pool (node) | 16 | 0 | 16 | 0 | 0 | 0 | 0 | +14.7% |
| Compute / AI / Cloud | Container Resources | compute_pool (server) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Compute / AI / Cloud | Cross-Cluster, Multi-Region & Edge | compute_pool (node) | 15 | 0 | 9 | 6 | 0 | 0 | 0 | +10.5% |
| Compute / AI / Cloud | DPU SmartNIC & Programmable IO | compute_pool (fabric) | 12 | 0 | 0 | 12 | 0 | 0 | 0 | +0.0% |
| Compute / AI / Cloud | Distributed Cluster Managers | compute_pool (batch) | 15 | 0 | 0 | 7 | 0 | 8 | 0 | -0.3% |
| Compute / AI / Cloud | GPU Fabric & RDMA | compute_pool (fabric) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Compute / AI / Cloud | HPC & Distributed Compute | compute_pool (batch) | 16 | 0 | 0 | 8 | 0 | 8 | 0 | -0.1% |
| Compute / AI / Cloud | Host CPU & Memory | compute_pool (cpu_host) | 16 | 8 | 0 | 8 | 0 | 0 | 0 | +1.4% |
| Compute / AI / Cloud | Kubernetes Dynamic Device Allocation | compute_pool (gpu) | 8 | 0 | 0 | 8 | 0 | 0 | 0 | +0.0% |
| Compute / AI / Cloud | Kubernetes Placement & Scheduling | compute_pool (server) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Compute / AI / Cloud | Kubernetes Workload Scaling | compute_pool (server) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Compute / AI / Cloud | NVIDIA GPU Hardware | compute_pool (gpu) | 15 | 4 | 0 | 11 | 0 | 0 | 0 | +0.0% |
| Compute / AI / Cloud | Node Fleet & Karpenter-Class Control | compute_pool (node) | 16 | 0 | 13 | 3 | 0 | 0 | 0 | +14.3% |
| Compute / AI / Cloud | OpenShift & Machine API | compute_pool (node) | 9 | 0 | 5 | 4 | 0 | 0 | 0 | +13.3% |
| Compute / AI / Cloud | Work Admission & Demand Shaping | compute_pool (server) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Cache & Memory Services | compute_pool (server) | 15 | 0 | 0 | 15 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Commerce & Payment Systems | compute_pool (commerce) | 15 | 0 | 0 | 15 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Data Analytics & ETL | compute_pool (batch) | 15 | 0 | 0 | 11 | 0 | 4 | 0 | -0.1% |
| Distribution / Specialized | Database & Transactions | compute_pool (database) | 14 | 0 | 0 | 14 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Messaging & Streaming | compute_pool (server) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Network Routing & Switching | compute_pool (network) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Observability & Telemetry | compute_pool (server) | 6 | 0 | 0 | 6 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Reliability, Security & Recovery | compute_pool (server) | 12 | 0 | 0 | 12 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Runtime & Application | compute_pool (server) | 15 | 0 | 0 | 15 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Search, Indexing & Vector DB | compute_pool (server) | 15 | 0 | 0 | 15 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Service Mesh & API Reliability | compute_pool (server) | 15 | 0 | 0 | 15 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Storage Block/File/Object | compute_pool (storage) | 16 | 0 | 0 | 16 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Telecom RAN & Edge Radio | compute_pool (ran) | 12 | 0 | 0 | 12 | 0 | 0 | 0 | +0.0% |
| Distribution / Specialized | Workflow, Logistics & Fulfillment | compute_pool (workflow) | 15 | 0 | 0 | 10 | 0 | 5 | 0 | -0.0% |
| Energy / Facility / Industrial | Building & Critical Environment HVAC | thermal_zone (building) | 12 | 8 | 0 | 1 | 1 | 2 | 0 | +0.1% |
| Energy / Facility / Industrial | Cooling, Chillers & Thermodynamics | thermal_zone (data_hall) | 15 | 5 | 0 | 2 | 2 | 6 | 0 | -0.1% |
| Energy / Facility / Industrial | Energy Storage & Microgrid | energy_storage (microgrid) | 16 | 0 | 2 | 9 | 0 | 5 | 0 | -0.0% |
| Energy / Facility / Industrial | Facility & Grid Optimization | energy_storage (facility) | 15 | 0 | 5 | 2 | 0 | 8 | 0 | -0.0% |
| Energy / Facility / Industrial | Grid Transmission & Distribution | process_loop (feeder_voltage) | 12 | 4 | 0 | 8 | 0 | 0 | 0 | +0.0% |
| Energy / Facility / Industrial | Industrial PLC & Process Automation | process_loop (process) | 14 | 6 | 0 | 8 | 0 | 0 | 0 | +0.0% |
| Energy / Facility / Industrial | PDU, UPS & Electrical Distribution | energy_storage (ups) | 14 | 0 | 0 | 5 | 0 | 9 | 0 | -0.0% |
| Energy / Facility / Industrial | Semiconductor Fab & Precision Manufacturing | process_loop (chamber) | 11 | 2 | 0 | 9 | 0 | 0 | 0 | +0.0% |
| Energy / Facility / Industrial | Water Wastewater & Pumping | process_loop (water) | 12 | 4 | 0 | 8 | 0 | 0 | 0 | +0.0% |
| Physics / Robotics / Autonomous | Automotive EV & Mobile Powertrain | motion_axis (ev_traction) | 12 | 0 | 0 | 11 | 1 | 0 | 0 | +0.0% |
| Physics / Robotics / Autonomous | Aviation & Autonomous Flight | motion_axis (flight_axis) | 16 | 4 | 3 | 3 | 4 | 2 | 0 | +0.0% |
| Physics / Robotics / Autonomous | Quantum Computing Control Simulation | compute_pool (qpu) | 16 | 0 | 0 | 10 | 0 | 6 | 0 | -0.2% |
| Physics / Robotics / Autonomous | Robotics Fleet & Warehouse Automation | compute_pool (robot_fleet) | 15 | 0 | 0 | 15 | 0 | 0 | 0 | +0.0% |
| Physics / Robotics / Autonomous | Robotics Motion Control | motion_axis (robot_joint) | 15 | 8 | 3 | 4 | 0 | 0 | 0 | +0.6% |
| Physics / Robotics / Autonomous | Spacecraft & Flight Software | motion_axis (reaction_wheel) | 14 | 4 | 4 | 4 | 0 | 2 | 0 | +1.1% |

## Largest gains and largest losses (single muscles, by mean work per energy)

| Muscle | Family | Knob | Label | Work per energy | Work | Violations (pp) |
|---|---|---|---|---:|---:|---:|
| mass_flow_setpoint | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +36.7% (+34.9 to +38.5) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| temperature_setpoint | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +36.6% (+34.4 to +38.8) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| pressure_setpoint | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +36.1% (+33.9 to +38.3) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| valve_position | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +35.3% (+33.2 to +37.4) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| tank_level_target | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +35.3% (+33.1 to +37.5) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| furnace_setpoint | Industrial PLC & Process Automation | setpoint | SUPERIOR WITHIN GUARDRAILS | +35.3% (+33.5 to +37.1) | +0.0% (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| machine_remediation | OpenShift & Machine API | capacity | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | +20.8% (+14.2 to +27.3) | -2.1% (-2.7 to -1.4) | +22.1 (+19.6 to +24.6) |
| boot_disk_class | Cloud VM & Capacity | capacity | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | +18.0% (+14.2 to +21.9) | -1.4% (-2.1 to -0.7) | +21.6 (+18.9 to +24.3) |
| cross_cluster_replication | Cross-Cluster, Multi-Region & Edge | capacity | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | +17.7% (+12.1 to +23.2) | -1.3% (-1.8 to -0.7) | +19.0 (+16.5 to +21.5) |
| nodepool_weight | Node Fleet & Karpenter-Class Control | setpoint | ENERGY IMPROVEMENT WITH SERVICE TRADEOFF | +17.3% (+12.5 to +22.1) | -1.5% (-2.1 to -0.9) | +21.0 (+18.8 to +23.2) |
| dispatch_priority | Workflow, Logistics & Fulfillment | admission | WORSE | -33.2% (-35.0 to -31.3) | -10.0% (-11.6 to -8.4) | +51.8 (+47.7 to +55.9) |
| workflow_backoff | Workflow, Logistics & Fulfillment | admission | WORSE | -32.9% (-34.3 to -31.5) | -9.8% (-11.2 to -8.4) | +56.6 (+52.3 to +60.9) |
| workflow_retry | Workflow, Logistics & Fulfillment | admission | WORSE | -30.0% (-32.5 to -27.4) | -21.1% (-23.4 to -18.7) | +59.8 (+54.4 to +65.2) |
| workflow_timeout | Workflow, Logistics & Fulfillment | admission | WORSE | -28.9% (-33.5 to -24.3) | -10.5% (-12.4 to -8.7) | +48.0 (+37.5 to +58.4) |
| workflow_admission | Workflow, Logistics & Fulfillment | admission | WORSE | -27.5% (-31.4 to -23.6) | -17.4% (-19.8 to -15.0) | +53.1 (+43.9 to +62.4) |
| scheduler_fair_share | HPC & Distributed Compute | admission | WORSE | -24.3% (-26.4 to -22.2) | -0.0% (-0.0 to -0.0) | +35.5 (+31.6 to +39.3) |
| etl_concurrency | Data Analytics & ETL | admission | WORSE | -24.3% (-27.2 to -21.3) | +0.0% (-0.0 to +0.0) | +28.2 (+25.0 to +31.4) |
| parallel_io_budget | HPC & Distributed Compute | admission | WORSE | -22.8% (-24.0 to -21.7) | -0.0% (-0.0 to +0.0) | +33.8 (+30.9 to +36.7) |
| job_preemption | HPC & Distributed Compute | admission | WORSE | -22.8% (-23.7 to -22.0) | -0.0% (-0.0 to +0.0) | +38.3 (+36.2 to +40.4) |
| deadline_pressure | Distributed Cluster Managers | admission | WORSE | -22.7% (-24.6 to -20.9) | +0.0% (-0.0 to +0.0) | +33.6 (+30.6 to +36.6) |

## Validity

- Watch equal to native and the kill switch handing back the knob: 656 of 656 muscles; 5 of 5 organisms.
- Raw per-seed contrasts: `REALMS.json`. One row per muscle: `MUSCLES.csv`. Fingerprints: `RUN.json`, `SHA256SUMS.txt`.
