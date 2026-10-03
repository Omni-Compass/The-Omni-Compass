# OmniCompass: the seat, the receipt, and the fee

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Handoff chapter, from the founder's working conversations (with Grok, 2026-10-01/02), checked against the repository.
Where a sentence is a design aim rather than what the code does today, or a figure that is not yet measured, the
check column says so. Nothing in this chapter adds a result: every number that is a result names the file it comes
from.

## What Omni is

OmniCompass is the governor. It is the process running on the processor, and the chip executes it. The card, the
replica count, the rack cap, the joint and the feeder are the levers: the muscles. Omni reads the meters, steps a
bounded loop, and writes only the lever it is allowed to write. When it stops, it puts that lever back.

It is not the chip, not the card and not Kubernetes. It is the brain on the host, writing through a bolt.

*Governor* is the machine word. A governor on a steam engine did not build the engine and did not turn the shaft. It
watched the speed and moved the throttle so the speed stayed in a band. The plant does the work: the chip, the card,
the pods, the job. Omni reads a meter, writes one lever, and puts that lever back.

## The loop

| The chapter says | The code today | Check |
|---|---|---|
| Omni reads the plant's meters and maps them to the state E, U, S | `omnicompass/adapter.py`, `observe_vector` and `assimilate` | matches |
| It computes the drift with the command at zero, then raw = −drift + K_P·(σ − U), clipped to the authority before the step | `omnicompass/core.py`, `control_command`: `u = clip(−f_U(x,t) + KP·(σ − U), ±U_AUTHORITY)` | matches |
| It holds that same u through every RK4 stage and does not rewrite U afterwards | `core.py`, `macro_step`: one `u` per micro step, passed unchanged into all four RK4 stages; U is never overwritten | matches (proved: `docs/TRACKING_THEOREM.md`) |
| It writes the clipped command u to the lever | **Not today.** The frozen live governor runs the engine with u = 0 (`macro_step(..., target=None)`) and uses u only as its convergence signal (`push = u / U_AUTHORITY`). The lever is set by the allocation law and the nervous system's authority (`omnicompass/nervous_system.py`). | **design aim**, see "What to strengthen" |
| On exit it restores the lever | kill switch: `omni_controller/controller.py` restore; the GPU bench restores and reads back the start limit; the realm harness checks every knob is handed back | matches |

So the step the chapter describes is the engine's own step, and it is proved. Writing u itself onto a lever, through
an output map with a gain in watts (or replicas) per unit of u, is a further mechanism. It is not what produced the
results below.

## Wiring

A wrist wire moves the wrist. It does not move a finger that has its own tendon unless that tendon is also wired.

The card's clock wire goes to the NVIDIA driver. The replica wire goes to the Kubernetes API. The scheduler's wire goes
to the kubelet. Those wires already exist and do not pass through Omni. Omni is an added process, and a tendon is
connected to it only if the output map writes that lever and the input map reads it back.

A power-limit write can make the driver drop clocks. That is a side effect on one finger, not the replica nerve, which
keeps running on its own path unless a second line is connected. The cluster starts its own wires: the API server
accepts a replica write, the scheduler places the pod, the kubelet starts it, the driver moves the clocks, and HPA, if
installed, is its own process. Omni joins those nerves. It is a client of the plant, not its origin.

## Four realms, five organisms

1. Compute / AI / Cloud: GPU server, Kubernetes, the card, the job.
2. Physics / Robotics / Autonomous: joint, servo, PLC, car, line.
3. Energy / Facility / Industrial: rack, cooling, PDU, battery.
4. Distribution / Specialized: network, feeder, logistics.
5. The whole organism: all 656 canonical muscles, each once, one clock.

A muscle may sit in more than one realm. Every realm stands on the same spine (Kubernetes, machines, GPUs and CPUs,
network, storage, observability, security, cooling, electrical distribution), and then has its own domain muscles. The
fifth run holds each of the 656 once.

Each organism is shown native, then with Omni, on the same membership, the same seed and the same clock: two receipts.
The core does not change when the lever changes.

| Check | |
|---|---|
| Built | `realms/` (round 3): spine of 190 muscles in all four realms; organisms of 345, 262, 282, 337 and 656 (`docs/REALM_MUSCLES.md`) |
| Result | Whole organism +0.1% work per energy, SUPERIOR WITHIN GUARDRAILS; the realms pay in service when they share the spine (`results/realms/REALMS.md`) |
| Limit | These are modelled plants (evidence S / rung E2). A catalog row is not a tendon. GitHub can host the compute organism for real (kind, and the GPU on a rented card); facility, machine and grid need their own hosts |
| Open | The 656 is a working catalog, not a census: `docs/realm_study/` checks it against the real systems' documentation and industry practice (waves 1 and 2 done; wave 3 maps every row) |

## Evidence rungs

| Rung (chapter) | Class (repository, `docs/EVIDENCE_LEDGER.md`) | Meaning |
|---|---|---|
| E0 | design | the written spec |
| E1 | T / V | deterministic tests and proofs: Python against the C++ twin, the tracking theorem |
| E2 | S | simulation on a made plant (the realms, the fleet and GPU models) |
| E3 | L | real software: Kubernetes on kind, no card (sets 22 and 23) |
| E4 | P | a physical meter: the card's own power reading (the GPU bench; first run on an NVIDIA A10, 2026-10-02, `results/gpu/run-20261002T082232Z/GPU_REPS.md`; the corrected governor not yet run on a card) |

A result does not climb a rung by itself. The four realms are plants; E1 to E4 are how hard the proof is on whichever
plant is run.

## What blocked the card

The hash did not stop the card. A Python–C++ mismatch can fail a test after a machine has started the job; it cannot
stop GitHub from handing out a machine, because the runner is chosen before the code runs. The verify job started and
failed (fixed since: it is green), and separately the GPU job never got a machine.

The organisation's and enterprise's settings show no GPU runner and no option to create one (checked 2026-10-02), so no
budget could start it. The run therefore moves to a rented card (`scripts/gpu_rented_run.sh`, one command).

## The bake-off that exists

Set 23 (`results/live/LIVE_REPS_23.md`, run 36940088922): real Kubernetes, ten pairs, fifteen minutes an arm, the same
open-loop work, native against Omni, six kind workers, order rotated.

| Gauge | Native | Omni | Change |
|---|---:|---:|---:|
| Response, 95th percentile (ms) | 327.3 | 123.8 | −62.2% |
| Response, 99th percentile (ms) | 503.4 | 169.3 | −66.4% |
| Response, mean (ms) | 146.6 | 80.1 | −45.4% |
| Failed requests | 0 | 0 | 0 |
| HPA replicas, mean | 8.51 | 5.40 | −36.6% |
| Workers in service | 6 | 4.28 | −28.7% |
| Pods started | 4.7 | 1.7 | −63.8% |
| Pod start wait (s) | 18.6 | 3.8 | −79.6% |
| CPU, service plus Omni (cores) | 0.903 | 0.894 | −1.0% (no difference) |
| Energy, workers still on (Wh, declared model) | 159.0 | 158.7 | −0.2% (no difference) |

The same requests were sent and none failed. They were answered faster, on fewer copies, at the same bill. Kind
leaves every worker powered, so the watt line stays flat. Parking a worker and waking it again was tried; the churn ate
the saving (`docs/CLAIMS_REGISTER.md`, C17), so that path is closed on this plant.

Arithmetic, not a result: if a run finishes 5% more work, nineteen runs do what twenty used to (20 / 1.05 = 19.05).

## The chip

The card is the meter that can move the electric bill, and the meter that can move output.

Energy on the chip is the integral of power.draw. The same pile can be spent two ways:
- **Output:** more finished work on the same bill. The cap stays near where the native arm left it, the draw stays in
  the same band, and heat gets no new reason to rise.
- **The bill:** a lower enforced limit, the job still finishes, and joules fall.

A company short of cards spends it on output. A company paying for GPU hours with spare capacity spends it on the bill.
A company against a building power cap splits it. The bench's primary outcome, work per joule, counts both, and its
table prints requests and joules separately, so the receipt shows which way the pile went (`tools/gpu_reps.py`).

For the pile to be real:
- the cap has to bind;
- the write has to be enforced by the driver, and the enforced limit read back;
- the job has to finish;
- the limit has to be restored on exit, so the next native arm is not still capped.

All four are in the bench and its preregistration (`docs/GPU_PREREGISTRATION.md`, amendments 1–3).

## The babysitting tax

The electric bill is the small pile. The babysitting tax is the people and tools kept on the clock to watch the
levers, reset a cap, and stop the muscles fighting. A card's real cost is usually the card and the hours it sat idle or
late, not the electrons.

What fills the seat today is a person: someone sets the cap, someone gets the page when it is left down, someone turns
it back after the run or the crash. The product takes that knob and that page.

## What we found nobody selling

We found no published product that does all of the following across compute, machines, facility and grid as one
governor:
- reads all of their meters into one state;
- holds one clipped command through the step;
- puts each lever back when the run stops, and prints both receipts.

Borg, Twine and OpenShift govern compute. AWS is a cloud. Turbonomic covers the IT stack. Tesla runs the car, the
battery and the factory as separate software. Each covers more than one thing as a company, not four realms as one
governor.

Omni on such a stack does not replace it: Borg remains the muscle. This is a market observation from public material,
not a claim tested here.

## The bill

Run the stack native and print the receipt. Run the same stack with Omni and print the receipt. The difference is the
pile, and the fee is 20 percent of it.

On a stack that costs $100, a 10 percent win is $10. The fee is $2, and the customer keeps $8. In general, the fee is
0.2 × (measured win) × (spend). A gain and a cut are the same difference, read from opposite sides. Do not add CPU,
GPU and babysitting percentages into one bill: the invoice is one pile.

**Check:** the 10 percent is an example, not a measured win. What is measured so far:
- on Kubernetes, response time −62% at the same energy (set 23);
- in simulation, +0.1% work per energy for the whole organism (realm round 3);
- on a card, nothing yet: the GPU bench is the first real-meter number.

Revenue figures should be computed from the measured win on each customer's own receipt. The per-company table in the
working draft (2% of each company's published infrastructure spend) assumed a 10% win everywhere, and several of its
spend figures do not match the companies' published capital expenditure. It is left out of the repository until both
are sourced.

## What to strengthen

1. **Wire the output map.** u becomes one lever, read back and restored, with the start value, the written value and
   the value after a kill printed on the receipt. The GPU bench already records the start limit, every write and its
   read-back, and the restored limit. A u-to-lever output map (a gain in watts or replicas per unit of u) is a new
   mechanism. It would be preregistered and tested as its own arm, first in the realms, then on a card, never mixed
   into the frozen confirmation run.
2. **Keep the step as it is:** clip before the stage, hold u through RK4, do not rewrite U (proved:
   `docs/TRACKING_THEOREM.md`).
3. **Run native against Omni on the same membership for each realm.** Compute is the one GitHub can host for real;
   the other three are modelled until their hosts exist.
4. **Aim the chip at about 5% more finished work on the same bill**, cap unchanged and temperature no worse, or at
   fewer joules for the same work. The buyer chooses, and the receipt prints which.
