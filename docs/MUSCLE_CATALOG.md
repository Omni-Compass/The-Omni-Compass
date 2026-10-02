# The 656 Muscles: What Each Is For, and How It Is Wired

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

A **muscle** is one setting on one machine that already has its own control: a replica target, a node pool's size, a GPU's clock ceiling, a chiller's setpoint, a battery's reserve, a joint's effort. Omni-Compass does not replace that control. It reads the machine's meters, computes one bounded force with the bowl law, and moves the setting the machine already accepts, through a plug that reads the setting once before the first write, reads back every write, steps aside if another controller moves it, and puts it back at the end.

This chapter lists all 656 muscles of the catalog (`realms/catalog.csv`). For each one it says what kind of machine it is, which of the four kinds of knob it is, what Omni-Compass reads and does with it, how such a muscle is reached in a real stack, and which organisms it belongs to. The plants behind the benchmark numbers are models of these machines (evidence class **S**); a muscle in this list is wired on a real system only through the levels and the checks of the manual (chapters 8 and 9). See `DISCLOSURES.md`.

## How to read an entry

**The four kinds of knob.**

- **capacity**: how much of the machine is in service (replicas, instances, units, speed). Omni-Compass writes it.
- **admission**: what is let in (queues, rate limits, admission control). Omni-Compass reads it and leaves it to its own controller in the current law; it is counted, never written.
- **power**: the power share or limit the machine may draw. Omni-Compass writes it inside its cover.
- **setpoint**: the target the machine's own loop holds (a temperature, a reserve, a process value). Omni-Compass moves it inside its safe band.

**The five kinds of plant.** Every muscle is modelled on one of five plants, each with its own service reading and lever:

| Plant | What it is | What Omni-Compass reads | What Omni-Compass moves |
|---|---|---|---|
| `compute_pool` | a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs | how far its queue and its load sit toward the service line (queue or lateness, and load above half) | the capacity it may use: its replica or instance count (through its autoscaler's target or floor), its power share, or one unit given back through the release gate |
| `thermal_zone` | a data hall or building zone cooled by chillers, air handlers or fans | its temperature against its limit | its supply setpoint (colder is more cooling), its power share, or one cooling unit given back when the room has margin |
| `energy_storage` | a battery, UPS or microgrid store with a load and a grid connection | its draw on the grid connection and its reserve | its reserve setpoint (how much charge it holds back); its power limit is left native |
| `motion_axis` | a motor-driven axis: a robot joint, a flight-control surface, a reaction wheel, a traction motor | its tracking error and its load | its speed and effort share, or its power share |
| `process_loop` | a regulated process: a temperature, pressure, flow, level, voltage or composition held at a setpoint | how far the process sits from its band | its setpoint within its safe band, its actuator range, or its power share |

**The organisms.** The 656 muscles build six organisms: each of the four realms (every muscle whose realm list includes it), the four stacked with every duplicate kept (1,226), and the whole tower with every muscle once (656). A muscle of the shared spine sits in all four realms.

| Organism | Muscles |
|---|---:|
| Compute / AI / Cloud | 345 |
| Physics / Robotics / Autonomous | 262 |
| Energy / Facility / Industrial | 282 |
| Distribution / Specialized | 337 |
| The four stacked, every duplicate kept | 1,226 |
| The whole tower, every muscle once | 656 |

**How a muscle is reached in a real stack.** The class of machine decides the wire:

| Class of machine | What it is | The wire in a real stack |
|---|---|---|
| `batch` | batch and queued jobs | the job queue (Kubernetes Jobs, Slurm, Spark) |
| `building` | a building zone | the building management system |
| `chamber` | a controlled chamber (clean room, kiln, reactor) | the PLC or DCS |
| `commerce` | a customer-facing service with bursts | the Kubernetes API |
| `cpu_host` | a CPU host whose clock and power can be set | Linux cpufreq and RAPL |
| `data_hall` | a data hall cooling plant | the building management system (BACnet, Modbus) or its command line |
| `database` | a database cluster | the database operator (replicas, connection pools) |
| `ev_traction` | an electric vehicle traction motor | the vehicle's motor controller (CAN; modelled only) |
| `fabric` | a high-speed fabric (RDMA, DPU, SmartNIC) | the fabric manager's API |
| `facility` | a facility battery behind the meter | the energy management system |
| `feeder_voltage` | a distribution feeder's voltage | the distribution management system (IEC 61850, DNP3; modelled only) |
| `flight_axis` | a flight-control axis | the flight controller (modelled only) |
| `gpu` | GPU serving with a response-time target | nvidia-smi (clock ceiling and power limit) or the serving autoscaler |
| `gpu_batch` | GPU training and batch work | nvidia-smi, the job scheduler's pause and resume |
| `microgrid` | a microgrid battery and loads | the inverter or energy management system (IEEE 2030.5, SunSpec, OpenADR) |
| `network` | network routing and switching | the network controller (SDN, routing API) |
| `node` | a fleet of machines or VMs that boot in minutes | the node pool's size command (Karpenter, Cluster Autoscaler, MachineSet, cloud ASG) |
| `process` | an industrial process loop | the PLC or DCS (OPC UA, EtherNet/IP, PROFINET) |
| `qpu` | a quantum or specialised accelerator queue | the accelerator's job queue |
| `ran` | a radio access network cell or site | the RAN controller (O-RAN interfaces) |
| `reaction_wheel` | a spacecraft reaction wheel | the attitude controller (modelled only) |
| `robot_fleet` | a fleet of robots or vehicles taking tasks | the fleet manager's dispatch API |
| `robot_joint` | a robot joint servo | the robot controller (ROS 2, EtherCAT, the drive's fieldbus) |
| `server` | an application service on servers or pods | the Kubernetes API (HPA target and floor, pod resize) |
| `storage` | block, file or object storage | the storage system's QoS and tiering API |
| `ups` | an uninterruptible power supply | the UPS and PDU management interface (SNMP, Modbus) |
| `water` | a water or pumping process | the SCADA system (Modbus, DNP3) |
| `workflow` | a workflow or pipeline engine | the workflow engine's concurrency settings |

Wires marked *modelled only* exist as plants in the benchmark and are not built for live use.

## The shared spine: 190 muscles in all four realms

The machines every realm stands on: servers, machines, GPUs and CPUs, network, storage, observability, security, cooling and electrical distribution. Each spine muscle is part of every realm's organism, counted once in the tower and four times in the stack.

### Cloud VM & Capacity (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `node` (a fleet of machines or VMs that boot in minutes), reached through the node pool's size command (Karpenter, Cluster Autoscaler, MachineSet, cloud ASG). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 97 | vm count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 98 | vm size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 99 | vm start stop | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 100 | vm migrate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 101 | instance family | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 102 | asg min | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 103 | asg max | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 104 | spot mix | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 105 | reservation mix | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 106 | zone selection | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 107 | region selection | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 108 | architecture selection | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 109 | accelerator selection | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 110 | boot disk class | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 111 | placement group | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 112 | interruption response | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |

### Container Resources (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 33 | cpu request | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 34 | cpu limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 35 | memory request | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 36 | memory limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 37 | ephemeral storage | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 38 | hugepages | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 39 | io weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 40 | pids limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 41 | memory high | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 42 | memory reclaim | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 43 | swap limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 44 | cgroup io max | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 45 | cpu weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 46 | cpu quota | admission | reads it; left to its own controller | all four realms; stack; tower |
| 47 | cpuset | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 48 | runtime class | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |

### Host CPU & Memory (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `cpu_host` (a CPU host whose clock and power can be set), reached through Linux cpufreq and RAPL. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 113 | cpufreq min | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 114 | cpufreq max | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 115 | rapl package power | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 116 | uncore frequency | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 117 | energy perf preference | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 118 | cpu idle policy | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 119 | memory bandwidth | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 120 | numa balance | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 121 | irq affinity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 122 | llc allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 123 | memory pressure gate | admission | reads it; left to its own controller | all four realms; stack; tower |
| 124 | page reclaim rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 125 | transparent hugepages | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 126 | core online offline | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 127 | thermal throttle policy | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 128 | host power profile | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |

### Kubernetes Placement & Scheduling (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 49 | node selector | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 50 | node affinity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 51 | pod anti affinity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 52 | topology spread | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 53 | numa placement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 54 | gpu topology | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 55 | storage locality | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 56 | network locality | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 57 | taint toleration | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 58 | priority class | admission | reads it; left to its own controller | all four realms; stack; tower |
| 59 | preemption policy | admission | reads it; left to its own controller | all four realms; stack; tower |
| 60 | device claim | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 61 | failure domain spread | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 62 | scheduler backoff | admission | reads it; left to its own controller | all four realms; stack; tower |
| 63 | gang admission | admission | reads it; left to its own controller | all four realms; stack; tower |
| 64 | deschedule | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |

### Kubernetes Workload Scaling (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 17 | replicas | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 18 | hpa cpu target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 19 | hpa memory target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 20 | hpa custom target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 21 | vpa apply | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 22 | scale to zero | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 23 | keda threshold | admission | reads it; left to its own controller | all four realms; stack; tower |
| 24 | rollout rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 25 | max surge | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 26 | max unavailable | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 27 | deployment pause resume | admission | reads it; left to its own controller | all four realms; stack; tower |
| 28 | rollout abort | admission | reads it; left to its own controller | all four realms; stack; tower |
| 29 | pod eviction | admission | reads it; left to its own controller | all four realms; stack; tower |
| 30 | pdb policy | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 31 | scheduler queue priority | admission | reads it; left to its own controller | all four realms; stack; tower |
| 32 | api priority fairness | admission | reads it; left to its own controller | all four realms; stack; tower |

### NVIDIA GPU Hardware (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `gpu` (GPU serving with a response-time target), reached through nvidia-smi (clock ceiling and power limit) or the serving autoscaler. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 129 | gpu allocate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 130 | gpu power limit | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 131 | gpu sm clock | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 132 | gpu memory clock | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 133 | gpu persistence mode | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 134 | gpu compute mode | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 135 | mig mode | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 136 | mig geometry | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 137 | gpu timeslice | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 138 | gpu mps | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 139 | gpu quarantine | admission | reads it; left to its own controller | all four realms; stack; tower |
| 140 | gpu reset | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 141 | gpu thermal limit | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 142 | gpu ecc response | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 143 | gpu job power budget | admission | reads it; left to its own controller | all four realms; stack; tower |

### Node Fleet & Karpenter-Class Control (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `node` (a fleet of machines or VMs that boot in minutes), reached through the node pool's size command (Karpenter, Cluster Autoscaler, MachineSet, cloud ASG). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 65 | node desired | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 66 | node pool min | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 67 | node pool max | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 68 | node provision | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 69 | node cordon | admission | reads it; left to its own controller | all four realms; stack; tower |
| 70 | node drain | admission | reads it; left to its own controller | all four realms; stack; tower |
| 71 | node consolidate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 72 | node replace | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 73 | node shutdown | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 74 | node power on | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 75 | nodepool weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 76 | disruption budget | admission | reads it; left to its own controller | all four realms; stack; tower |
| 77 | consolidation policy | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 78 | consolidate after | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 79 | expire after | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 80 | capacity class | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |

### Network Routing & Switching (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `network` (network routing and switching), reached through the network controller (SDN, routing API). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 225 | lb weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 226 | route weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 227 | rate limit | admission | reads it; left to its own controller | all four realms; stack; tower |
| 228 | bandwidth limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 229 | qos class | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 230 | connection limit | admission | reads it; left to its own controller | all four realms; stack; tower |
| 231 | failover route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 232 | nic rate limit | admission | reads it; left to its own controller | all four realms; stack; tower |
| 233 | nic queue count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 234 | queue discipline | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 235 | congestion control | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 236 | egress budget | admission | reads it; left to its own controller | all four realms; stack; tower |
| 237 | ingress budget | admission | reads it; left to its own controller | all four realms; stack; tower |
| 238 | ecmp weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 239 | path selection | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 240 | network isolation | admission | reads it; left to its own controller | all four realms; stack; tower |

### Observability & Telemetry (6 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 373 | collector memory limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 374 | export concurrency | admission | reads it; left to its own controller | all four realms; stack; tower |
| 376 | cardinality budget | admission | reads it; left to its own controller | all four realms; stack; tower |
| 377 | retention window | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 378 | remote write queue | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 379 | telemetry shed | admission | reads it; left to its own controller | all four realms; stack; tower |

### Reliability, Security & Recovery (12 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 385 | restart | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 386 | rollback | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 388 | traffic divert recovery | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 389 | degraded mode | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 390 | actuator freeze | admission | reads it; left to its own controller | all four realms; stack; tower |
| 391 | workload isolate | admission | reads it; left to its own controller | all four realms; stack; tower |
| 393 | credential rotation gate | admission | reads it; left to its own controller | all four realms; stack; tower |
| 394 | policy enforcement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 395 | rate abuse gate | admission | reads it; left to its own controller | all four realms; stack; tower |
| 396 | fault domain isolate | admission | reads it; left to its own controller | all four realms; stack; tower |
| 397 | backup trigger | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 400 | kill switch | admission | reads it; left to its own controller | all four realms; stack; tower |

### Storage Block/File/Object (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `storage` (block, file or object storage), reached through the storage system's QoS and tiering API. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 257 | volume size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 258 | iops limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 259 | throughput limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 260 | replica count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 261 | storage tier | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 262 | volume placement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 263 | snapshot trigger | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 264 | rebalance | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 265 | recovery rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 266 | backfill rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 267 | compaction pressure | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 268 | cache allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 269 | object replication | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 270 | erasure code profile | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 271 | storage admission | admission | reads it; left to its own controller | all four realms; stack; tower |
| 272 | degraded storage gate | admission | reads it; left to its own controller | all four realms; stack; tower |

### Cooling, Chillers & Thermodynamics (15 muscles)

Each is a data hall or building zone cooled by chillers, air handlers or fans; its class is `data_hall` (a data hall cooling plant), reached through the building management system (BACnet, Modbus) or its command line. Omni-Compass reads its temperature against its limit. It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 545 | supply air temperature | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 546 | return air target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 547 | coolant supply temperature | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 548 | coolant flow | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 549 | pump speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 550 | fan speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 551 | chiller setpoint | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 552 | compressor authority | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 553 | cooling tower fan | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 554 | cooling capacity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 555 | rack thermal budget | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 556 | gpu thermal envelope | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 557 | cpu thermal envelope | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 558 | thermal workload migrate | admission | reads it; left to its own controller | all four realms; stack; tower |
| 559 | thermal load shed | admission | reads it; left to its own controller | all four realms; stack; tower |

### PDU, UPS & Electrical Distribution (14 muscles)

Each is a battery, UPS or microgrid store with a load and a grid connection; its class is `ups` (an uninterruptible power supply), reached through the UPS and PDU management interface (SNMP, Modbus). Omni-Compass reads its draw on the grid connection and its reserve. It belongs to every organism.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 529 | server power cap | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 530 | rack power cap | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 531 | pdu branch power limit | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 532 | pdu outlet control | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 534 | ups operating mode | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 535 | ups charge rate | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 536 | ups discharge rate | power | holds the power share inside its cover; full at once past the wall | all four realms; stack; tower |
| 537 | phase balance | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 538 | load transfer | admission | reads it; left to its own controller | all four realms; stack; tower |
| 539 | reactive power target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 540 | voltage target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | all four realms; stack; tower |
| 541 | generator dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | all four realms; stack; tower |
| 542 | electrical isolation | admission | reads it; left to its own controller | all four realms; stack; tower |
| 543 | breaker trip gate | admission | reads it; left to its own controller | all four realms; stack; tower |

## Realm: Compute / AI / Cloud (155 muscles of its own, 345 in its organism with the spine)

### AI Inference Serving (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `gpu` (GPU serving with a response-time target), reached through nvidia-smi (clock ceiling and power limit) or the serving autoscaler. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 161 | model replicas | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 162 | model route weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Compute; stack; tower |
| 163 | model load | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 164 | model unload | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 165 | model instance count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 166 | continuous batching | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 167 | max batch size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 168 | batch queue delay | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 169 | inference concurrency | admission | reads it; left to its own controller | Compute; stack; tower |
| 170 | inference max tokens | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 171 | kv cache budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 172 | prefix cache budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 173 | speculative decode budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 174 | model precision | power | holds the power share inside its cover; full at once past the wall | Compute; stack; tower |
| 175 | inference priority | admission | reads it; left to its own controller | Compute; stack; tower |
| 176 | inference slo gate | admission | reads it; left to its own controller | Compute; stack; tower |

### AI Training (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `gpu_batch` (GPU training and batch work), reached through nvidia-smi, the job scheduler's pause and resume. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 177 | training workers | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 178 | global batch size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 179 | microbatch size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 180 | gradient accumulation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 181 | data parallelism | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 182 | tensor parallelism | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 183 | pipeline parallelism | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 184 | expert parallelism | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 185 | checkpoint interval | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Compute; stack; tower |
| 186 | checkpoint trigger | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 187 | training preempt | admission | reads it; left to its own controller | Compute; stack; tower |
| 188 | training gang size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 189 | elastic worker count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 190 | straggler mitigation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 191 | training precision | power | holds the power share inside its cover; full at once past the wall | Compute; stack; tower |
| 192 | compute comm overlap | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |

### Cross-Cluster, Multi-Region & Edge (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `node` (a fleet of machines or VMs that boot in minutes), reached through the node pool's size command (Karpenter, Cluster Autoscaler, MachineSet, cloud ASG). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 609 | multi cluster dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 610 | region dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 611 | zone dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 612 | edge dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 613 | cloud capacity class | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 614 | workload migrate region | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 615 | data residency gate | admission | reads it; left to its own controller | Compute; stack; tower |
| 616 | latency region gate | admission | reads it; left to its own controller | Compute; stack; tower |
| 617 | cost region gate | admission | reads it; left to its own controller | Compute; stack; tower |
| 618 | carbon region gate | admission | reads it; left to its own controller | Compute; stack; tower |
| 619 | global failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 620 | federation quota | admission | reads it; left to its own controller | Compute; stack; tower |
| 621 | cross cluster replication | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 622 | edge offload | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 623 | global admission | admission | reads it; left to its own controller | Compute; stack; tower |

### DPU SmartNIC & Programmable IO (12 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `fabric` (a high-speed fabric (RDMA, DPU, SmartNIC)), reached through the fabric manager's API. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| AUDIT-0021 | dpu pf tx rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0022 | dpu vf tx rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0023 | dpu sf tx rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0024 | dpu bandwidth share | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0025 | dpu qos group | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0026 | sriov vf count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0027 | smartnic flow steering | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0028 | smartnic offload enable | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0029 | dpu cpu budget | admission | reads it; left to its own controller | Compute; stack; tower |
| AUDIT-0030 | dpu memory budget | admission | reads it; left to its own controller | Compute; stack; tower |
| AUDIT-0031 | dpu service placement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0032 | dpu failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |

### Distributed Cluster Managers (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `batch` (batch and queued jobs), reached through the job queue (Kubernetes Jobs, Slurm, Spark). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 209 | task admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 210 | task priority | admission | reads it; left to its own controller | Compute; stack; tower |
| 211 | resource reservation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 212 | cluster quota | admission | reads it; left to its own controller | Compute; stack; tower |
| 213 | task preemption | admission | reads it; left to its own controller | Compute; stack; tower |
| 214 | binpack pressure | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 215 | spread pressure | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 216 | gang schedule | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 217 | worker allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 218 | maintenance evacuation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 219 | oversubscription | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 220 | resource reclaim | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 221 | queue fairness | admission | reads it; left to its own controller | Compute; stack; tower |
| 222 | deadline pressure | admission | reads it; left to its own controller | Compute; stack; tower |
| 223 | scheduler retry | admission | reads it; left to its own controller | Compute; stack; tower |

### GPU Fabric & RDMA (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `fabric` (a high-speed fabric (RDMA, DPU, SmartNIC)), reached through the fabric manager's API. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 145 | nvlink placement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 146 | nvswitch route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 147 | gpu fabric quarantine | admission | reads it; left to its own controller | Compute; stack; tower |
| 148 | rdma bandwidth | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 149 | rdma route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 150 | nic affinity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 151 | collective concurrency | admission | reads it; left to its own controller | Compute; stack; tower |
| 152 | collective algorithm | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 153 | collective chunk size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 154 | rank placement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 155 | gpudirect policy | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 156 | congestion response | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 157 | rail selection | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 158 | fabric failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 159 | communication priority | admission | reads it; left to its own controller | Compute; stack; tower |
| 160 | fabric isolation | admission | reads it; left to its own controller | Compute; stack; tower |

### HPC & Distributed Compute (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `batch` (batch and queued jobs), reached through the job queue (Kubernetes Jobs, Slurm, Spark). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 193 | job slots | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 194 | mpi ranks | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 195 | rank mapping | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 196 | node allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 197 | job walltime | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 198 | job priority | admission | reads it; left to its own controller | Compute; stack; tower |
| 199 | job preemption | admission | reads it; left to its own controller | Compute; stack; tower |
| 200 | checkpoint restart | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 201 | parallel io budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 202 | collective budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 203 | accelerator share | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 204 | cpu gpu ratio | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Compute; stack; tower |
| 205 | memory per rank | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 206 | scratch budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 207 | scheduler fair share | admission | reads it; left to its own controller | Compute; stack; tower |
| 208 | backfill policy | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |

### Kubernetes Dynamic Device Allocation (8 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `gpu` (GPU serving with a response-time target), reached through nvidia-smi (clock ceiling and power limit) or the serving autoscaler. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| AUDIT-0001 | dra device class selection | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0002 | dra claim capacity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0003 | dra claim sharing | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0004 | dra device taint | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0005 | dra device eviction | admission | reads it; left to its own controller | Compute; stack; tower |
| AUDIT-0006 | dra binding readiness | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0007 | dra binding failure response | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| AUDIT-0008 | dra device configuration | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Compute; stack; tower |

### OpenShift & Machine API (9 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `node` (a fleet of machines or VMs that boot in minutes), reached through the node pool's size command (Karpenter, Cluster Autoscaler, MachineSet, cloud ASG). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 85 | machine remediation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 88 | machine health gate | admission | reads it; left to its own controller | Compute; stack; tower |
| 89 | mcp pause | admission | reads it; left to its own controller | Compute; stack; tower |
| 90 | mcp max unavailable | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 91 | node config rollout | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 92 | operator reconcile budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 93 | cluster version pacing | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 94 | infra machine admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 95 | machine failure domain | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |

### Quantum Computing Control Simulation (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `qpu` (a quantum or specialised accelerator queue), reached through the accelerator's job queue. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 593 | qubit mapping | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 594 | circuit admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 595 | shot allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 596 | circuit scheduling | admission | reads it; left to its own controller | Compute; stack; tower |
| 597 | gate scheduling | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 598 | pulse amplitude | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 599 | pulse duration | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Compute; stack; tower |
| 600 | pulse phase | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 601 | pulse frequency | power | holds the power share inside its cover; full at once past the wall | Compute; stack; tower |
| 602 | coupling control | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 603 | reset scheduling | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 604 | measurement scheduling | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 605 | dynamical decoupling | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 606 | noise aware routing | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Compute; stack; tower |
| 607 | error mitigation budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 608 | quantum queue priority | admission | reads it; left to its own controller | Compute; stack; tower |

### Work Admission & Demand Shaping (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Compute / AI / Cloud.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 1 | api concurrency | admission | reads it; left to its own controller | Compute; stack; tower |
| 2 | queue concurrency | admission | reads it; left to its own controller | Compute; stack; tower |
| 3 | queue backpressure | admission | reads it; left to its own controller | Compute; stack; tower |
| 4 | job admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 5 | batch admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 6 | inference admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 7 | load shed | admission | reads it; left to its own controller | Compute; stack; tower |
| 8 | priority gate | admission | reads it; left to its own controller | Compute; stack; tower |
| 9 | tenant admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 10 | burst limit | admission | reads it; left to its own controller | Compute; stack; tower |
| 11 | deadline admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 12 | work budget | admission | reads it; left to its own controller | Compute; stack; tower |
| 13 | request queue limit | admission | reads it; left to its own controller | Compute; stack; tower |
| 14 | retry admission | admission | reads it; left to its own controller | Compute; stack; tower |
| 15 | background work gate | admission | reads it; left to its own controller | Compute; stack; tower |
| 16 | maintenance work gate | admission | reads it; left to its own controller | Compute; stack; tower |

## Realm: Physics / Robotics / Autonomous (72 muscles of its own, 262 in its organism with the spine)

### Automotive EV & Mobile Powertrain (12 muscles)

Each is a motor-driven axis: a robot joint, a flight-control surface, a reaction wheel, a traction motor; its class is `ev_traction` (an electric vehicle traction motor), reached through the vehicle's motor controller (CAN; modelled only). Omni-Compass reads its tracking error and its load. Its home realm is Physics / Robotics / Autonomous.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| AUDIT-0045 | traction torque limit | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0046 | regen braking level | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0047 | battery charge limit | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0048 | battery discharge limit | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0049 | battery thermal target | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0050 | motor thermal limit | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0051 | vehicle speed envelope | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| AUDIT-0052 | energy recovery target | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0053 | auxiliary power budget | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0054 | fast charge current | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0055 | fast charge voltage | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| AUDIT-0056 | vehicle safe state | admission | reads it; left to its own controller | Physics; stack; tower |

### Aviation & Autonomous Flight (16 muscles)

Each is a motor-driven axis: a robot joint, a flight-control surface, a reaction wheel, a traction motor; its class is `flight_axis` (a flight-control axis), reached through the flight controller (modelled only). Omni-Compass reads its tracking error and its load. Its home realm is Physics / Robotics / Autonomous.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 481 | throttle envelope | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 482 | attitude target | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 483 | attitude rate target | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 484 | velocity target | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 485 | altitude target | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 486 | waypoint authority | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 487 | flight hold | admission | reads it; left to its own controller | Physics; stack; tower |
| 488 | return to home | admission | reads it; left to its own controller | Physics; stack; tower |
| 489 | land action | admission | reads it; left to its own controller | Physics; stack; tower |
| 490 | mission admission | admission | reads it; left to its own controller | Physics; stack; tower |
| 491 | geofence response | admission | reads it; left to its own controller | Physics; stack; tower |
| 492 | failsafe selection | admission | reads it; left to its own controller | Physics; stack; tower |
| 493 | battery reserve threshold | admission | reads it; left to its own controller | Physics; stack; tower |
| 494 | actuator saturation envelope | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 495 | flight mode transition | admission | reads it; left to its own controller | Physics; stack; tower |
| 496 | flight termination safe state | admission | reads it; left to its own controller | Physics; stack; tower |

### Robotics Fleet & Warehouse Automation (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `robot_fleet` (a fleet of robots or vehicles taking tasks), reached through the fleet manager's dispatch API. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Physics / Robotics / Autonomous.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 449 | robot dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 450 | task assignment | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 451 | traffic reservation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 452 | robot route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 453 | charging dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 454 | battery reserve | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 455 | elevator request | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 456 | door request | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 457 | conveyor speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 458 | agv speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 459 | warehouse zone admission | admission | reads it; left to its own controller | Physics; stack; tower |
| 460 | robot quarantine | admission | reads it; left to its own controller | Physics; stack; tower |
| 461 | fleet failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 462 | human safe stop | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 463 | fleet concurrency | admission | reads it; left to its own controller | Physics; stack; tower |

### Robotics Motion Control (15 muscles)

Each is a motor-driven axis: a robot joint, a flight-control surface, a reaction wheel, a traction motor; its class is `robot_joint` (a robot joint servo), reached through the robot controller (ROS 2, EtherCAT, the drive's fieldbus). Omni-Compass reads its tracking error and its load. Its home realm is Physics / Robotics / Autonomous.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 433 | joint position | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 434 | joint velocity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 435 | joint acceleration | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 436 | joint effort | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 437 | cartesian velocity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 438 | trajectory speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 439 | trajectory acceleration | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 440 | jerk limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 441 | collision margin | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 442 | force limit | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 443 | gripper force | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 444 | locomotion speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 445 | steering angle | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 446 | braking force | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 447 | balance correction | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |

### Spacecraft & Flight Software (14 muscles)

Each is a motor-driven axis: a robot joint, a flight-control surface, a reaction wheel, a traction motor; its class is `reaction_wheel` (a spacecraft reaction wheel), reached through the attitude controller (modelled only). Omni-Compass reads its tracking error and its load. Its home realm is Physics / Robotics / Autonomous.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 497 | space command admission | admission | reads it; left to its own controller | Physics; stack; tower |
| 499 | flight task schedule | admission | reads it; left to its own controller | Physics; stack; tower |
| 500 | space mode transition | admission | reads it; left to its own controller | Physics; stack; tower |
| 501 | payload duty cycle | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 502 | communication allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 503 | space power budget | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 504 | space thermal command | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 505 | attitude command envelope | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 506 | reaction wheel allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 507 | rcs authority | power | holds the power share inside its cover; full at once past the wall | Physics; stack; tower |
| 508 | safe mode transition | admission | reads it; left to its own controller | Physics; stack; tower |
| 509 | watchdog recovery | admission | reads it; left to its own controller | Physics; stack; tower |
| 510 | instrument activation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Physics; stack; tower |
| 511 | fault isolation | admission | reads it; left to its own controller | Physics; stack; tower |

## Realm: Energy / Facility / Industrial (92 muscles of its own, 282 in its organism with the spine)

### Building & Critical Environment HVAC (12 muscles)

Each is a data hall or building zone cooled by chillers, air handlers or fans; its class is `building` (a building zone), reached through the building management system. Omni-Compass reads its temperature against its limit. Its home realm is Energy / Facility / Industrial.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| AUDIT-0081 | zone temperature target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0082 | zone airflow | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0083 | ahu fan speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0084 | damper position | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0085 | economizer position | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0086 | boiler setpoint | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0087 | heat pump mode | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0088 | humidity target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0089 | occupancy ventilation | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0090 | building demand limit | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| AUDIT-0091 | thermal storage dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0092 | hvac emergency mode | admission | reads it; left to its own controller | Energy; stack; tower |

### Energy Storage & Microgrid (16 muscles)

Each is a battery, UPS or microgrid store with a load and a grid connection; its class is `microgrid` (a microgrid battery and loads), reached through the inverter or energy management system (IEEE 2030.5, SunSpec, OpenADR). Omni-Compass reads its draw on the grid connection and its reserve. Its home realm is Energy / Facility / Industrial.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 513 | battery charge power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 514 | battery discharge power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 515 | battery soc reserve | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 516 | grid import limit | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 517 | grid export limit | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 518 | pv curtailment | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 519 | ev charge power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 520 | heat pump power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 521 | electrolyzer power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 522 | microgrid demand limit | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 523 | peak shaving | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 524 | time of use schedule | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 525 | energy load shed | admission | reads it; left to its own controller | Energy; stack; tower |
| 526 | flex load admission | admission | reads it; left to its own controller | Energy; stack; tower |
| 527 | storage dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 528 | microgrid emergency reserve | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |

### Facility & Grid Optimization (15 muscles)

Each is a battery, UPS or microgrid store with a load and a grid connection; its class is `facility` (a facility battery behind the meter), reached through the energy management system. Omni-Compass reads its draw on the grid connection and its reserve. Its home realm is Energy / Facility / Industrial.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 561 | facility power budget | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 562 | utility demand limit | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 563 | demand response | admission | reads it; left to its own controller | Energy; stack; tower |
| 564 | electricity price gate | admission | reads it; left to its own controller | Energy; stack; tower |
| 565 | carbon intensity gate | admission | reads it; left to its own controller | Energy; stack; tower |
| 566 | renewable dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 567 | generator start stop | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 568 | site battery dispatch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 569 | pue target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 570 | cooling power budget | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 571 | it power budget | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 572 | rack power allocation | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 573 | facility peak guard | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 574 | grid frequency response | admission | reads it; left to its own controller | Energy; stack; tower |
| 575 | facility islanding | admission | reads it; left to its own controller | Energy; stack; tower |

### Grid Transmission & Distribution (12 muscles)

Each is a regulated process: a temperature, pressure, flow, level, voltage or composition held at a setpoint; its class is `feeder_voltage` (a distribution feeder's voltage), reached through the distribution management system (IEC 61850, DNP3; modelled only). Omni-Compass reads how far the process sits from its band. Its home realm is Energy / Facility / Industrial.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| AUDIT-0033 | capacitor bank switch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0034 | voltage regulator tap | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0035 | transformer tap | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0036 | inverter real power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| AUDIT-0037 | inverter reactive power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| AUDIT-0038 | feeder voltage target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0039 | feeder load transfer | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0040 | distribution storage dispatch | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0041 | demand response dispatch | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0042 | frequency droop setpoint | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0043 | grid protection mode | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0044 | grid restoration sequence | admission | reads it; left to its own controller | Energy; stack; tower |

### Industrial PLC & Process Automation (14 muscles)

Each is a regulated process: a temperature, pressure, flow, level, voltage or composition held at a setpoint; its class is `process` (an industrial process loop), reached through the PLC or DCS (OPC UA, EtherNet/IP, PROFINET). Omni-Compass reads how far the process sits from its band. Its home realm is Energy / Facility / Industrial.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 465 | plc cycle authority | admission | reads it; left to its own controller | Energy; stack; tower |
| 466 | machine cell admission | admission | reads it; left to its own controller | Energy; stack; tower |
| 467 | valve position | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 468 | pump flow | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 469 | compressor speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 470 | heater power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| 471 | furnace setpoint | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 472 | pressure setpoint | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 473 | temperature setpoint | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 474 | mass flow setpoint | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 475 | tank level target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| 476 | conveyor rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 477 | feed rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| 478 | purge vent action | admission | reads it; left to its own controller | Energy; stack; tower |

### Semiconductor Fab & Precision Manufacturing (11 muscles)

Each is a regulated process: a temperature, pressure, flow, level, voltage or composition held at a setpoint; its class is `chamber` (a controlled chamber (clean room, kiln, reactor)), reached through the PLC or DCS. Omni-Compass reads how far the process sits from its band. Its home realm is Energy / Facility / Industrial.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| AUDIT-0057 | tool job dispatch | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0058 | wafer route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0059 | chamber recipe selection | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0060 | chamber temperature | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0061 | chamber pressure | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0062 | gas flow | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0063 | rf power | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| AUDIT-0064 | vacuum pump speed | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0065 | robot transfer rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0066 | lot priority | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0068 | tool quarantine | admission | reads it; left to its own controller | Energy; stack; tower |

### Water Wastewater & Pumping (12 muscles)

Each is a regulated process: a temperature, pressure, flow, level, voltage or composition held at a setpoint; its class is `water` (a water or pumping process), reached through the SCADA system (Modbus, DNP3). Omni-Compass reads how far the process sits from its band. Its home realm is Energy / Facility / Industrial.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| AUDIT-0069 | pump speed water | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Energy; stack; tower |
| AUDIT-0070 | valve position water | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0071 | reservoir level target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0072 | line pressure target | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0073 | flow target water | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Energy; stack; tower |
| AUDIT-0074 | aeration rate | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| AUDIT-0075 | chemical dose rate | power | holds the power share inside its cover; full at once past the wall | Energy; stack; tower |
| AUDIT-0076 | filtration backwash | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0077 | lift station dispatch | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0078 | leak isolation | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0079 | water demand shed | admission | reads it; left to its own controller | Energy; stack; tower |
| AUDIT-0080 | water emergency shutdown | admission | reads it; left to its own controller | Energy; stack; tower |

## Realm: Distribution / Specialized (147 muscles of its own, 337 in its organism with the spine)

### Cache & Memory Services (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 305 | cache size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 306 | cache ttl | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Distribution; stack; tower |
| 307 | cache eviction policy | admission | reads it; left to its own controller | Distribution; stack; tower |
| 308 | cache replicas | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 309 | cache sharding | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 310 | cache prefetch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 311 | cache writeback rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 312 | cache admission | admission | reads it; left to its own controller | Distribution; stack; tower |
| 313 | hot key isolation | admission | reads it; left to its own controller | Distribution; stack; tower |
| 314 | cache connection limit | admission | reads it; left to its own controller | Distribution; stack; tower |
| 315 | cache memory limit | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 316 | cache compression | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 317 | cache warmup | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 318 | cache failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 319 | cache flush rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |

### Commerce & Payment Systems (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `commerce` (a customer-facing service with bursts), reached through the Kubernetes API. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 401 | payment admission | admission | reads it; left to its own controller | Distribution; stack; tower |
| 402 | payment concurrency | admission | reads it; left to its own controller | Distribution; stack; tower |
| 403 | payment retry | admission | reads it; left to its own controller | Distribution; stack; tower |
| 404 | payment timeout | admission | reads it; left to its own controller | Distribution; stack; tower |
| 405 | fraud review gate | admission | reads it; left to its own controller | Distribution; stack; tower |
| 406 | authorization route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 407 | processor route weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Distribution; stack; tower |
| 408 | transaction queue limit | admission | reads it; left to its own controller | Distribution; stack; tower |
| 409 | idempotency window | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Distribution; stack; tower |
| 410 | order reservation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 411 | inventory hold | admission | reads it; left to its own controller | Distribution; stack; tower |
| 412 | checkout load shed | admission | reads it; left to its own controller | Distribution; stack; tower |
| 413 | refund queue rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 414 | settlement batch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 415 | payment failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |

### Data Analytics & ETL (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `batch` (batch and queued jobs), reached through the job queue (Kubernetes Jobs, Slurm, Spark). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 338 | executor size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 339 | dynamic allocation min | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 340 | dynamic allocation max | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 341 | shuffle partitions | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 342 | shuffle bandwidth | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 343 | etl concurrency | admission | reads it; left to its own controller | Distribution; stack; tower |
| 344 | stage parallelism | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 345 | query slots | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 346 | spill threshold | admission | reads it; left to its own controller | Distribution; stack; tower |
| 347 | cache fraction | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Distribution; stack; tower |
| 348 | batch interval | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Distribution; stack; tower |
| 349 | stream backpressure | admission | reads it; left to its own controller | Distribution; stack; tower |
| 350 | data locality wait | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 351 | speculation policy | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 352 | analytics admission | admission | reads it; left to its own controller | Distribution; stack; tower |

### Database & Transactions (14 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `database` (a database cluster), reached through the database operator (replicas, connection pools). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 273 | db replicas | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 275 | db memory | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 276 | db cache | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 277 | query concurrency | admission | reads it; left to its own controller | Distribution; stack; tower |
| 278 | read route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 279 | shard placement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 280 | db failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 281 | replication lag gate | admission | reads it; left to its own controller | Distribution; stack; tower |
| 282 | db write throttle | admission | reads it; left to its own controller | Distribution; stack; tower |
| 283 | db pool resize | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 284 | transaction concurrency | admission | reads it; left to its own controller | Distribution; stack; tower |
| 285 | lock timeout | admission | reads it; left to its own controller | Distribution; stack; tower |
| 286 | checkpoint rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 287 | vacuum compaction rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |

### Messaging & Streaming (16 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 289 | partition count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 290 | partition placement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 291 | producer quota | admission | reads it; left to its own controller | Distribution; stack; tower |
| 292 | consumer quota | admission | reads it; left to its own controller | Distribution; stack; tower |
| 293 | broker io quota | admission | reads it; left to its own controller | Distribution; stack; tower |
| 294 | message retention | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 295 | queue depth limit | admission | reads it; left to its own controller | Distribution; stack; tower |
| 296 | consumer concurrency | admission | reads it; left to its own controller | Distribution; stack; tower |
| 297 | producer batch size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 298 | fetch batch size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 299 | rebalance rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 300 | replication factor | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 301 | retry backoff | admission | reads it; left to its own controller | Distribution; stack; tower |
| 302 | dead letter divert | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 303 | stream priority | admission | reads it; left to its own controller | Distribution; stack; tower |
| 304 | broker failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |

### Runtime & Application (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 353 | worker count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 354 | thread pool | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 355 | jvm heap | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 356 | gc budget | admission | reads it; left to its own controller | Distribution; stack; tower |
| 357 | connection pool runtime | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 358 | application cache size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 359 | runtime memory | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 360 | async concurrency | admission | reads it; left to its own controller | Distribution; stack; tower |
| 361 | event loop workers | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 362 | process count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 363 | request timeout | admission | reads it; left to its own controller | Distribution; stack; tower |
| 364 | background workers | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 365 | runtime cpu budget | admission | reads it; left to its own controller | Distribution; stack; tower |
| 366 | runtime io budget | admission | reads it; left to its own controller | Distribution; stack; tower |
| 367 | runtime restart | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |

### Search, Indexing & Vector DB (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 321 | index workers | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 322 | index refresh rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 323 | segment merge rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 324 | search concurrency | admission | reads it; left to its own controller | Distribution; stack; tower |
| 325 | search timeout | admission | reads it; left to its own controller | Distribution; stack; tower |
| 326 | shard count | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 327 | shard replication | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 328 | shard rebalance | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 329 | vector search k | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 330 | vector batch size | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 331 | embedding workers | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 332 | index memory budget | admission | reads it; left to its own controller | Distribution; stack; tower |
| 333 | query route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 334 | hot shard isolation | admission | reads it; left to its own controller | Distribution; stack; tower |
| 335 | search admission | admission | reads it; left to its own controller | Distribution; stack; tower |

### Service Mesh & API Reliability (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `server` (an application service on servers or pods), reached through the Kubernetes API (HPA target and floor, pod resize). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 241 | circuit breaker | admission | reads it; left to its own controller | Distribution; stack; tower |
| 242 | retry budget | admission | reads it; left to its own controller | Distribution; stack; tower |
| 243 | service timeout | admission | reads it; left to its own controller | Distribution; stack; tower |
| 244 | service concurrency | admission | reads it; left to its own controller | Distribution; stack; tower |
| 245 | connection pool | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 246 | traffic divert | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 247 | traffic mirror | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 248 | canary weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Distribution; stack; tower |
| 249 | outlier ejection | admission | reads it; left to its own controller | Distribution; stack; tower |
| 250 | health threshold | admission | reads it; left to its own controller | Distribution; stack; tower |
| 251 | dns traffic weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Distribution; stack; tower |
| 252 | session affinity | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 253 | request hedging | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 254 | fault injection gate | admission | reads it; left to its own controller | Distribution; stack; tower |
| 255 | service failover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |

### Telecom RAN & Edge Radio (12 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `ran` (a radio access network cell or site), reached through the RAN controller (O-RAN interfaces). Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| AUDIT-0009 | ran connection admission | admission | reads it; left to its own controller | Distribution; stack; tower |
| AUDIT-0010 | ran ue handover | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| AUDIT-0011 | ran cell traffic steering | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| AUDIT-0012 | ran slice resource budget | admission | reads it; left to its own controller | Distribution; stack; tower |
| AUDIT-0013 | ran prb allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| AUDIT-0014 | ran scheduler weight | setpoint | moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not | Distribution; stack; tower |
| AUDIT-0015 | ran tx power | power | holds the power share inside its cover; full at once past the wall | Distribution; stack; tower |
| AUDIT-0016 | ran antenna tilt | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| AUDIT-0017 | ran carrier enable | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| AUDIT-0018 | ran cell sleep | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| AUDIT-0019 | ran du cu placement | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| AUDIT-0020 | ran fronthaul budget | admission | reads it; left to its own controller | Distribution; stack; tower |

### Workflow, Logistics & Fulfillment (15 muscles)

Each is a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs; its class is `workflow` (a workflow or pipeline engine), reached through the workflow engine's concurrency settings. Omni-Compass reads how far its queue and its load sit toward the service line (queue or lateness, and load above half). Its home realm is Distribution / Specialized.

| # | Muscle | Knob | What Omni-Compass does with it | Organisms |
|---:|---|---|---|---|
| 417 | workflow admission | admission | reads it; left to its own controller | Distribution; stack; tower |
| 418 | workflow worker rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 419 | task queue rate | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 420 | workflow retry | admission | reads it; left to its own controller | Distribution; stack; tower |
| 421 | workflow backoff | admission | reads it; left to its own controller | Distribution; stack; tower |
| 422 | workflow timeout | admission | reads it; left to its own controller | Distribution; stack; tower |
| 423 | inventory allocation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 424 | fulfillment route | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 425 | warehouse queue | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 426 | carrier selection | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 427 | dispatch priority | admission | reads it; left to its own controller | Distribution; stack; tower |
| 428 | shipment batch | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 429 | route replan | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 430 | sla escalation | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |
| 431 | compensation action | capacity | holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate | Distribution; stack; tower |

