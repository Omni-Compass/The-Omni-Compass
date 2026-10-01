# Omni-Compass Domain Map

Every system Omni-Compass can sit on, what it reads, what it pushes, the reflexes that bound it, and where it stands.

## 1. The connector pattern

Omni-Compass is the same engine on every muscle. Each muscle gets one connector with five parts:

| Part | Role | Example (compute) |
|---|---|---|
| Afferent (sense) | What the muscle reports | load, pending work, power, heat |
| Engine | Equations (1)-(7) turn readings into state: error E, coherence U, pressure I_U, stress S, bath B | same six-state engine everywhere |
| Efferent (push) | The equation (2) law and allocation law drive the muscle toward convergence | node count, HPA target, power cap |
| Reflex (shield) | Hard limits checked before any push | never below pod requests, step limits, power limit |
| Kill | Control returns to the muscle's own controllers | restore HPA targets, observe only |

Fit tiers used below:
- **Direct**: Omni can govern the muscle as a supervisory controller.
- **Supervisory**: Omni governs budgets, schedules and envelopes; the muscle's own real-time controller stays in charge of fast inner loops.
- **Advisory**: regulated or safety-critical; Omni recommends until certified (IEC 61508, DO-178C, ISO 26262, medical and financial regulation).
- **Not Omni's problem**: a different kind of problem; stated so no one claims otherwise.

Status: **Wired** (in code, verified), **Partial**, **Open** (connector not yet built).

## 2. Digital infrastructure

| Muscle | Reads | Pushes | Reflexes | Fit | Status |
|---|---|---|---|---|---|
| Compute nodes and node pools | load, pending pods, requests | node count, park or power off | request floor, step limit | Direct | **Wired** |
| Pods via HPA | utilisation, replicas | HPA target | bounds 50-95% | Direct | **Wired** |
| Power caps | watts, site limit | per-node caps | site power limit (I4) | Direct | **Wired** (harness) |
| Heat | temperatures | feeds decisions | thermal limit | Direct | **Sensed** |
| GPUs / accelerators | utilisation, power, temperature, memory | power caps, clocks, partitioning (MIG), packing | temperature, job safety | Direct | Open |
| CPU power states | per-socket power (RAPL) | frequency scaling, sleep states | latency floor | Direct | Open |
| Memory | used vs requested | request right-sizing | OOM margin | Direct | Open |
| Storage | I/O load, latency, capacity | tiering, placement, volume scaling | durability, replica counts | Supervisory | Open |
| Network, load balancers | traffic, congestion, latency | routing weights, traffic shift | capacity per link | Direct | Partial |
| CDN / edge | cache hit, origin load | cache and origin routing | freshness | Direct | Open |
| Batch and HPC job queues | queue depth, deadlines | admission, priority, time shifting | deadline guarantees | Direct | Open |
| Multi-cluster / multi-region | load, cost, carbon per region | placement | data residency | Direct | Open |
| Deployments | release health | pause, roll back | never skip required checks | Direct | Partial (stack harness) |
| Databases, stateful services | load, replication lag | read replicas, pools | consistency limits | Supervisory | Open |
| Control plane health | API latency, etcd load | rate of Omni's own actions | never overload the API | Direct | Open |
| Tenant quotas | usage per tenant | who may grow | fairness bounds | Direct | Open |
| Hardware health | disk and memory errors | early drain of failing machines | availability floor | Direct | Open |
| Observability pipelines | data volume, cost | sampling, retention | required audit data | Direct | Open |
| Security posture | policy blocks | block expansion during holds | I1 | Direct | Partial (sensed) |

## 3. AI

| Muscle | Reads | Pushes | Reflexes | Fit | Status |
|---|---|---|---|---|---|
| Training clusters | GPU power, progress, network | power caps, packing, checkpoint timing | never kill a run mid-step | Direct | Open (gpu vessels in harness) |
| Training power smoothing | synchronised power swings | ramp limits, staggering | grid ramp limits | Direct | Open |
| Inference serving | request rate, latency, queue, GPU memory | replicas, batch size, GPU sharing | latency SLO | Direct | Open |
| Model routing and cost | cost per request, quality signals | route to smaller or larger models, token budgets | quality floor | Direct | Open |
| Model releases | evaluation results, drift, errors | gate, pause, roll back a model | release gates | Direct | Open |
| Data pipelines, vector databases | backlog, freshness | scaling, scheduling | freshness bounds | Direct | Open |
| AI agents: containment | actions, spend, resources, network use | CPU, memory, network and spend caps, tool permissions | hard caps, instant kill | Direct | Open |
| Carbon-aware AI | grid price and carbon intensity | when and where training runs | deadlines | Direct | Open |

### AI alignment: what Omni can and cannot do

Alignment has two parts, and only one is Omni's.

| Part | What it means | Omni's role |
|---|---|---|
| **Value alignment** | The model itself wants and does what people intend: honest, safe, helpful behaviour learned in training | **Not Omni's problem.** A governor outside the model cannot make the model's goals or judgement correct. |
| **Control and containment** | Whatever the model wants, it can only act within bounds: resources, permissions, spend, network reach, a kill that works | **Direct.** This is a governance problem: sense what the agent is doing, bound what it may spend and touch, revoke instantly, keep an audit trail. |

Omni-Compass can be the boundary layer AI runs inside. It cannot be the thing that makes AI trustworthy. Claims must keep that line.

## 4. Facilities and energy

| Muscle | Reads | Pushes | Reflexes | Fit | Status |
|---|---|---|---|---|---|
| Cooling plant | inlet temperatures, chiller load | setpoints, fan curves, chiller staging | inlet temperature limits | Direct | Open |
| Building HVAC | zone temperatures, occupancy | setpoints, schedules | comfort bounds | Direct | Open |
| Facility power distribution | PDU and UPS load | limits for the shield | breaker limits | Supervisory | Open |
| On-site batteries and generators | state of charge, grid state | charge and discharge | reserve floor | Supervisory | Open |
| Power grids: demand response | grid signals, prices | shift or shed flexible load | contractual limits | Direct | Open |
| Microgrids, renewable smoothing | generation, storage, load | dispatch | frequency and voltage limits | Advisory to supervisory | Open |
| EV charging fleets | vehicle needs, grid capacity | charge schedules | departure deadlines | Direct | Open |
| Water and pumping | demand, pressure, energy price | pump schedules | pressure limits | Supervisory | Open |
| Grid frequency and protection | frequency, faults | none | certified protection systems | Advisory | Out of scope for control |

## 5. Physical operations

| Muscle | Pushes | Fit |
|---|---|---|
| Manufacturing lines | scheduling, energy, throughput balance | Supervisory |
| Warehouses and logistics | task allocation, fleet charging | Direct |
| Robot fleets | task assignment, charging, traffic, safety envelopes | Supervisory (never joint-level control) |
| Traffic signals, transit, rail scheduling | timing and schedules | Advisory (safety-certified) |
| Ports, shipping | berth and crane scheduling, energy | Supervisory |
| Agriculture, greenhouses, irrigation | water and climate setpoints | Direct |
| Mining, oil and gas | energy and scheduling only | Advisory (process safety) |
| Semiconductor fabs | tool scheduling, energy | Supervisory |

## 6. Science, space, biology, finance, health

| Domain | What Omni could govern | What it must not touch | Fit |
|---|---|---|---|
| HPC / supercomputers | job queues, power, cooling | none beyond the facility | Direct |
| Quantum-computer facilities | cryogenics energy, calibration scheduling | qubit control | Supervisory |
| Satellites and constellations | power, thermal, data budgets, scheduling | attitude and orbit control (flight software) | Supervisory |
| Spacecraft / astrodynamics | mission resource budgets | guidance and navigation | Advisory |
| Biology: lab automation, bioreactors | setpoints, schedules, cold chain | living-system interventions without validated models | Supervisory |
| Financial markets | risk limits, exposure caps, trading infrastructure | making trades, market control | Advisory (regulated) |
| Hospitals | bed, staffing and energy operations | medical devices, treatment | Advisory |
| Aviation, automotive, nuclear | monitoring | any direct control | Advisory (certification required) |

## 7. The problems everyone in computing has, and Omni's fit

| Problem | What Omni can do | Fit |
|---|---|---|
| Data-centre energy growth | right-size, park, cap, shift work in time and place | Direct |
| Cloud cost overruns and idle capacity | consolidate, right-size, remove padding | Direct |
| GPU scarcity and low GPU utilisation | pack jobs, share GPUs, schedule by priority | Direct |
| Heat and cooling limits | govern IT load and cooling plant together | Direct |
| Grid connection limits for new data centres | power smoothing, demand response, stay under contracted power | Direct |
| Carbon reporting and reduction | carbon-aware placement and timing, measured energy | Direct |
| On-call burnout and alert fatigue | hold the levers people turn at night; fewer, better alerts | Direct |
| Autoscalers fighting each other | single authority | Direct (proven in simulation) |
| Latency and SLO breaches under load | headroom governance, fast scheduling floor | Direct |
| Noisy neighbours, unfair tenants | quotas and growth permissions | Direct |
| Hardware failures | early drain on failure signs | Direct |
| Observability cost and data explosion | sampling and retention governance | Direct |
| Configuration drift | detect and gate, not rewrite configurations | Supervisory |
| Cold starts | pre-warming policy | Direct |
| Data egress costs | placement near data | Supervisory |
| Runaway AI agents and spend | caps, permissions, kill, audit | Direct |
| Security misconfiguration, supply-chain attacks | block risky expansion during holds | Partial (not a security scanner) |
| Model hallucination and bias | none | Not Omni's problem |
| AI value alignment | none | Not Omni's problem |
| Software bugs, technical debt, legacy migration | none | Not Omni's problem |
| Vendor lock-in | a single governor over mixed clouds | Supervisory |

## 8. Order of wiring

1. Digital infrastructure: GPUs, CPU power states, memory, storage, network, job queues, multi-region.
2. Facilities and energy: cooling plant, power distribution, batteries, demand response.
3. AI: training power smoothing, inference serving, model routing, agent containment.
4. Physical operations, then science and space as supervisors.
5. Regulated domains as advisors, until certified.

Each connector follows the same path as compute: wired, benchmarked against today's controls, verified, pre-registered, tested on held-out scenarios, then released.
