# GPU bench preregistration

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Written before any hardware trial. The confirmation run (`PHASE=confirm`) hashes this file with the code in
`FREEZE.json`; a change to either after the run starts invalidates it.

## Question

On one NVIDIA GPU serving a fixed, seeded request stream, does Omni-Compass holding the GPU power limit change the
successful work done per joule measured by the device, compared with the device left at its own limit?

Fixed here, before any smoke trial:
- the number of confirmation repetitions (10);
- the primary outcome;
- the guardrails;
- the analysis.

Nothing seen in smoke may change them.

## Two phases

1. **Smoke** (`PHASE=smoke`, any number of repetitions). Its purpose is to find faults in the harness, and to see
   whether the effect is large enough to be worth confirming. Smoke results are not published and are never
   reported as the result. After smoke, Omni's code may change.
2. **Confirmation** (`PHASE=confirm`). Omni's code is committed and frozen before the first trial. The script refuses
   to run if any frozen file has uncommitted changes, and the table marks the run invalid if a frozen file changes
   during it. No inspection, tuning or rerun between confirmation trials. If the confirmation fails, it is reported
   as failed; a new confirmation needs a new commit and a new run, and both runs are reported.

## Design

- **Arms:** native (no Omni), watch (Omni runs, may not write), omni (Omni writes the GPU power limit).
- **Repetitions:** 10 in confirmation, each with all three arms back to back, order rotated. Repetitions may run on
  separate machines of one GPU type (`REP_ONLY`, the GitHub workflow); the three arms of a repetition always share
  one machine, so every comparison is paired within a machine.
- **Per arm:** 60 s idle, then the pinned workload for 600 s plus 30 s drain.
- **Workload:** `tools/gpu_workload.py`, calibrated once at the start power limit before any arm. The seed is
  20260928, and the load phases are 30, 60, 80, 30, 60 and 30% of full-power capacity.

## Outcomes

- **Primary:** work per energy = requests served / GPU energy (kJ). GPU energy is `nvidia-smi` power.draw
  integrated over the arm's window.
- **Secondary:**
  - GPU energy;
  - energy per served request;
  - requests not served;
  - response time: mean, 95th and 99th percentile;
  - peak temperature;
  - CPU package energy (RAPL), where present;
  - where a smart plug is fitted (`WALL_METER`), whole-machine energy at the wall and work per wall kJ. The plug is
    read by the bench only, never by Omni. An arm whose plug readings have a gap over 5 s has no wall number.

## Analysis

- **Primary comparison:** omni against native, paired by repetition. Report the mean difference with a two-sided t
  95% interval.
- **Result:**
  - The result is *proven better* if the interval lies entirely above zero.
  - It is *proven worse* if the interval lies entirely below zero.
  - Otherwise it is *not proven*.
- **Guardrails, fixed now:** a better primary result counts only if Omni did not buy it with the work. Both
  guardrails must hold:
  - **Requests served:** the 95% interval of (omni − native) must not reach below −1% of native.
  - **95th-percentile response time:** the interval must not reach above +10% of native.

  If a guardrail fails, the verdict is *better on energy, fails the service guardrail*. That is a different product
  and is reported as such.
- **Watch against native:** reported as the cost of Omni being present. If watch differs from native on the primary
  outcome as much as omni does, the effect is not attributed to Omni's authority.

## Amendment 1 (2026-09-28, before any hardware trial; no smoke or confirmation data exist)

Added before any data, to make the chain from engine to plant identifiable. The question, the arms, the primary
outcome, the repetitions, and the two guardrails above are unchanged.

- **Three contrasts, all reported, each paired by repetition:** observation = watch − native; authority = omni −
  watch; total = omni − native (the primary comparison). A total effect is not attributed to Omni's authority where
  the observation contrast differs materially from zero.
- **Third guardrail, errors:** the 95% interval of (omni − native) requests *not* served must not reach above +1% of
  native requests served.
- **Result label, by rule, never by hand** (`tools/gpu_reps.py`, `label()`):
  - primary proven better, all three guardrails held: **SUPERIOR WITHIN GUARDRAILS**;
  - primary proven better, a guardrail failed: **ENERGY IMPROVEMENT WITH SERVICE TRADEOFF**;
  - primary not proven, all guardrails held: **NONINFERIOR / INCONCLUSIVE**;
  - primary not proven, a guardrail failed: **NOT ESTABLISHED**;
  - primary proven worse: **WORSE**;
  - any invalidity below: **INVALID**.
- **The card obeys enforced.power.limit.** The snapshot records power.limit, enforced.power.limit, default, min and
  max limits, persistence mode and power management. The bench refuses to start unless power management is Enabled.
  The bench samples enforced.power.limit where the driver reports it. The governor senses the enforced limit and reads
  back every write at once; it never writes clock locks.
- **Also invalid:** a native or watch arm whose enforced limit differs from the snapshot; a governor that exits
  nonzero (a refused start, or a write the device refused — that write ends the arm); smoke and confirmation
  repetitions mixed in one table.
- **Three receipts, kept apart.** A (governor, `audit.jsonl` decisions): telemetry consumed; the six-state reading
  (history-dependent, `state_observed`); the memoryless state the telemetry alone points to (`state_measured`); the
  U-channel command u evaluated on the evolved state (`u_push`); admissibility; requested and granted authority; shield
  bound; holds. B (actuator, `actuator` records): requested limit, return code, power.limit read back, enforced limit,
  delay to realization, override (enforced under requested), restoration. C (outcome, the bench alone): nvidia-smi
  power, joules, temperature, utilization, clock-limit reasons; the workload's requests, latency and failures. Omni
  never supplies its own outcome.
- **Secondary, descriptive (no verdict):**
  - actuator fidelity: r_act = read back − requested (mean and max absolute), delay (median, max), enforced-under-requested
    count, total variation of the realized limit, reversals, refused writes;
  - control effort: J_u = sum of abs(u_push) × decision interval; mean and max abs(u_push); saturations
    (abs(u_push) = 25); shield interventions (a bound other than the engine decided); holds;
  - representation fidelity: R_int = sqrt(mean over consecutive decision pairs of sum_k w_k (h(z_(k+1)) −
    F_h(h(z_k), u_k))_k²) over E, U, I_U, S, B, weights 1, with h the memoryless map and F_h the engine's own
    projection (`state_projected_next`); directional accuracy = share of pairs where sign(projected − current reading)
    equals sign(next measured − current measured), both movements at least 0.01, per state and by predicted size
    (0.01–0.03, 0.03–0.1, ≥ 0.1);
  - energy of the rest of the machine = wall − GPU − CPU package, only when all three meters measured the arm. A
    missing meter prints UNAVAILABLE, never a modelled substitute.
- **Smoke never enters confirmation.** A smoke run that changes any code or parameter is followed by: repair, the
  tests, a new freeze, and a confirmation collected from zero.

## The run is invalid, and reported as invalid, if

- the watch arm executes any power-limit write;
- a native or watch arm sees a power limit other than the snapshot;
- any arm ends at a limit other than the snapshot (the kill switch failed);
- Omni's frozen files change during the run;
- the confirmation runs on uncommitted code.

## Recorded for every Omni decision

Every decision is logged in `audit.jsonl`:
- the raw device telemetry: utilisation, draw, temperature, limit, SM clock, and clock-limit reasons where the driver
  reports them;
- the engine's six-state reading, the state it had projected for this moment, and the error against it;
- the projection for the next decision. This is the engine's own evolved state from the same step that sets the cap;
  no separate predictor was added for the experiment;
- whether change was admissible, the requested and granted authority, and which shield bound decided the limit;
- the limit written, and the requests served in the window.

## Amendment 2 (2026-09-28, before any hardware trial; no smoke or confirmation data exist)

Unchanged:
- the question;
- the arms;
- the primary outcome;
- the repetitions;
- the guardrails of amendment 1.

- **Watch must match native.** If the observation contrast (watch − native) on the primary outcome is proven in
  either direction, the label is **NOT ATTRIBUTABLE: WATCH DIFFERS FROM NATIVE** and no omni result is published.
- **One writer.** If the power limit ever reads a value that is neither Omni's last write nor the limit before it,
  another writer is present:
  - the governor stops writing for the rest of the run;
  - it leaves that writer's limit alone;
  - it exits 5;
  - the run is invalid.
- **Heat fails up.** While the device reports a thermal or hardware slowdown (clock-limit reason bits 0x8, 0x20,
  0x40, 0x80), no lower limit is written.
- **Credit per write (descriptive).** Each write owns the interval to the next. For that interval, the table records
  GPU joules and requests finished, Omni minus native, at the same moments of the same seeded stream. It records who
  decided the write: the engine, a floor, the busy gate, a reflex, heat, or the speed lock. The table says which rule
  produced the joules; a speed-lock result is not credited to the engine.
- **CPU side (secondary, never on the control path).** RAPL counters are read by domain name at both ends of each arm:
  - `package-N` is summed as CPU package; `dram` is summed separately;
  - `psys` is recorded and never added to either;
  - wrapping is undone with `max_energy_range_uj`;
  - a counter that went backwards without a known range, or is missing, prints UNAVAILABLE.
  - The governor never reads these counters.
- **Device energy counter (cross-check, secondary).** Where NVML reports it (Volta and newer), the card's total-energy
  counter is read at both ends of each arm, beside the integrated power.draw.
- **Card health (descriptive).** Uncorrected and corrected ECC error counts, and pages pending retirement, are read at
  both ends of each arm.
- **Workload plug.** Any workload may be served through `WORKLOAD_CMD` if it writes the pinned workload's files. It
  needs its own response-time target (`SLO_MS`). The command is recorded in the receipt. A confirmation names its
  workload before the first trial.

## Amendment 3 (2026-10-01, before any hardware trial; no smoke or confirmation data exist)

No GPU job has ever been given a machine (every gpu-bench run so far waited in the queue and was cancelled), so no
trial data exist. Unchanged:
- the question;
- the arms;
- the primary outcome;
- the repetitions;
- the guardrails, labels and invalidity rules of amendments 1 and 2.

- **Declared envelope, before any trial.** The buyer's service envelope is written to a file before the first trial
  and recorded with the run (`envelope.json` in the run folder and in every repetition):
  - `power_min_w`, the lowest watts Omni may set. Default (`tools/declare_envelope.py`): max(device minimum, 70% of the
    power limit read at declaration), rounded up to whole watts;
  - `power_max_w`, the power limit read at declaration;
  - optionally `slo_ms`, the response-time target; without it the target comes from calibration (10 bare service
    times), as before.
  - The bench refuses an envelope whose floor lies outside [device minimum, starting limit].
  - **The confirmation refuses to start without a declared envelope** (`scripts/gpu_paired.sh`, `ENVELOPE`).
- **Envelope floor.** The governor never sets the limit under `power_min_w` (`--floor-w`). When the floor is what
  lifted a write, the decision record names it (`decided_by`: envelope_floor), so no saving below the floor can be
  credited to the engine.
- **Outer controller holds.** When the card's own controller (board, BMC or system policy) already holds
  enforced.power.limit under the current limit, a lower write that would still sit above that enforced limit changes
  nothing on the card. It is not written; the decision record marks it (`outer_controller_holds`). Only a write that
  would actually bind, or a return upward, goes out. This is not another writer (amendment 2): the set limit is
  unchanged and the governor keeps running.
- **Narrow cards are reported as they are.** The device's own limit range is in the snapshot. On a card whose range is
  narrow (for example a 70 W card that accepts 60–70 W), the envelope is that narrow range; the result is reported for
  that card and range and not extrapolated to wider cards.

## Amendment 4 (2026-10-02, after an invalid smoke; no confirmation data exist)

The first smoke on a rented A10 (results/gpu/smoke-20261002T032459Z, never counted) was invalid by rule: two copies of
`scripts/gpu_rented_run.sh` had been started on the same machine, so both benches wrote the same card's power limit.
The native and watch arms saw limits they never wrote (116, 137 and 150 W), each governor refused to start beside the
other one (exit 5), and one kill-switch restore was undone by the other copy. The card also began at 116 W, a limit an
earlier start had left behind, not its 150 W default, so native itself ran capped (83% of samples). None of these
numbers measures Omni. The engine, the governor, the outcomes and the analysis are unchanged. The run script now:

- **runs once per machine:** it takes a lock and refuses to start while another copy runs;
- **runs alone on the card:** it refuses to start while any other process is using the GPU;
- **starts from the card's default limit:** it sets power.default_limit before the envelope is declared, so the
  envelope, the snapshot and every arm start from the card's own default, not from a limit an earlier run left behind.

## Amendment 5 (2026-10-02, before any valid hardware trial; the only smoke so far was invalid, amendment 4)

The Omni arm changes engine. The outcomes, the arms' order, the guardrails, the analysis and the validity rules are
unchanged.

- **The Omni arm holds two wires** (`omni_controller/gpu_bowl.py`, the bowl law of `omnicompass/bowl.py`): the clock
  ceiling (`nvidia-smi -lgc`, reset with `-rgc`; cover 35% of the top clock to the top), which sets how high the card's own boost may climb, and the power
  limit (`-pl`), the lid at what a fully busy card draws at that ceiling plus 10%, never under the declared envelope
  floor and never over the start limit. The service is read as one position between calm and the response-time line
  (the worse of p95 and utilization above half) and pulled to the middle; past 95% both wires go to full at once
  (fail up). The card's firmware keeps its own control; Omni sets only those two values. The earlier power-limit-only
  governor stays available (`OMNI_ENGINE=one_wire`) and is not the confirmation's arm.
- **Why, before the run:** on a modelled card (`results/sim/gpu_two_wire/`, evidence class S, seeds never used while
  tuning) the one-wire governor gave +0.1% work per energy and the two-wire engine +9.0%. That is a model; this run
  is the card's own meter.
- **The watch arm** runs the same two-wire engine in watch mode: it computes and records both wires and writes
  neither.
- **The clock range is reset before and after every arm** (`-rgc`), as the power limit already was; the run script
  resets it once at the start.
- **The wire check runs first** (`tools/gpu_wire_check.py`): the card's clock must follow a lowered ceiling down and
  come back up when reset, the power limit must read back what was set, the governor must hand both wires back when
  stopped and must leave a limit set by another writer alone (exit 5). If any step fails, nothing else runs and the
  check's report names the wire, the step and what the card said.
- **Wire check, corrected before any trial (2026-10-02):** on the A10 the first wire check failed at "3 up wire
  (follows up)" although the wire works: under the heavy check load the card's own 150 W limit already held it near
  990 MHz, so a ceiling at 60% of the top clock (1017 MHz) left no room for the clock to come back up above it. The
  check now reads the card's busy clock on its own first and locks at 60% of that. The governor likewise starts its
  ceiling at the clock the busy card actually runs (a ceiling above it holds nothing), and its clock cover is 35% of
  the top clock to the top. No trial had run.

## Amendment 6 (2026-10-02, after the first confirmation and before any further trial)

**What the first confirmation showed** (A10, commit `c908054`, `results/gpu/run-20261002T082232Z/`): work per energy
+3.6% (+2.7% to +4.5%, proven), the same requests served, no request lost, but the 95th-percentile response time
+58.5% (510 to 809 ms), so the response-time guardrail failed and the label by rule was ENERGY IMPROVEMENT WITH
SERVICE TRADEOFF. It stands as the result of that run.

**Why, from the card's own samples:** while busy the card ran at 736 to 768 MHz under Omni against 861 to 889 MHz on
its own, and spent about 30% more time busy for the same work; requests queued behind each slower one. Three faults
in the governor, not in the engine: (1) the position counted utilization above half as service trouble, so every
burst read as past the wall (fail up in 46% of decisions) and every quiet gap pulled the ceiling down, so each burst
began on a lowered clock; (2) the lid followed a curve from the top clock and sat at the 105 W envelope floor in 49 of
165 bowl decisions, under the 135 W the card itself draws while busy; (3) the ceiling's cover reached 35% of the top
clock, far under the clock the card's own power limit holds it at while busy.

**The Omni arm from now on** (`omni_controller/gpu_bowl.py`; the outcomes, arms, guardrails, analysis and validity
rules are unchanged):

- the position is response time only (p95 over 5 s, not 30 s); being busy is not a breach;
- **race while work waits:** at 95% utilization or more the ceiling goes to the top and the lid to the start limit;
  the bowl paces only the slack between bursts;
- **the card's own level, learned from its own meter** while the ceiling is at the top and the card is busy: its
  busy clock (median) and busy draw (90th percentile); until 15 such readings are in, neither wire moves;
- **speed floor:** the ceiling never goes under the card's own busy clock; **lid floor:** the lid never goes under the
  card's own busy draw plus 10%;
- fail up (past 95% of the line, or blind) is unchanged.

**On the modelled card, before any trial** (`results/sim/gpu_two_wire/`, seeds 5000 to 5009): p95 122.1 ms native,
123.7 ms with the corrected bowl; work per energy +8.2% (+6.3% to +10.1%); energy -7.5%; the median response 10.1 to
12.1 ms, slower in the quiet stretches the bowl paces. That is a model; the next trial is the card's own meter.

## Amendment 7 (2026-10-02, before any further trial)

The outcomes, arms, guardrails, analysis and validity rules are unchanged. The Omni arm of the confirmation runs the
**service** profile.

- **Two profiles, one switch** (`--profile`, `omni_controller/gpu_bowl.py`; the same in `realms/gpu_card.py`):
  - **service**, the default and the confirmation's arm: down gain 0.0125, the bowl's center at 0.4, the speed floor 3%
    above the card's own busy clock;
  - **batch**: down gain 0.015, center 0.5, the floor at the card's own busy clock, for work nobody waits on answer by
    answer. It may be run as a separate, declared confirmation (`OMNI_ARGS="--profile batch"`) and is reported as its
    own result, never pooled with service.
- **How service was chosen, on the model, before the trial** (20 paired seeds, 5000-5009 and 5100-5109; ratios
  summarised as the geometric mean of the per-seed ratios): down gains 0.01, 0.0125, 0.015, 0.0175 and 0.02 alone, and
  0.0125 to 0.0175 crossed with the bowl's center (0.4, 0.5), the speed floor (1.00, 1.03 of the card's own busy clock)
  and the race threshold (0.90, 0.95). The rule: the most work per energy at which no seed's p95 is more than 10% slower
  than native. Service (0.0125, 0.4, 1.03) gave work per energy +5.3% (+4.2 to +6.5), energy -5.0%, p95 -4.1% (-9.7 to
  +1.7), worst seed +9%, 0 of 20 seeds more than 10% slower, p99 -1.8%; its neighbours gave the same within a point.
  0.015 alone gave +6.2% but 3 of 20 seeds 10% to 48% slower at p95; 0.01 alone gave +3.8% with p95 -1.9%.
- **The ceiling moves in whole clock steps** (--min-change-mhz, 15 MHz), as the card's own clock does and as the model
  moves it: the force times the gain, as a share of the top clock, is rounded to whole steps, and a pull under half a
  step moves nothing and is not stored up.
- **The position reads the mean response time of the window** (as the model does), between the bare service time and
  the line; the 95th percentile at or past the line, or any failed request, is past the wall (fail up).
- **The model's report summarises ratios on the log scale** (`tools/run_gpu_card.py`): the arithmetic mean of per-seed
  percentages let one seed (+240%) stand for twenty.

## Amendment 8 (2026-10-03, before any further trial)

The outcomes, arms, guardrails, analysis and validity rules are unchanged, except as stated here.

- **Omni-Compass moves the card only where it measures that the card is no worse for it** (`omnicompass/verdict.py`, in
  `omni_controller/gpu_bowl.py` and `realms/gpu_card.py`). While the service is calm, the governor runs a paired trial:
  - first the ceiling at the top until 30 requests are measured;
  - then one 15 MHz step past the deepest step already allowed, until 30 more are measured.

  Each request's cost is the card's own time on it: the workload's new `service_ms` column, start to done, with the
  wait in the queue left out. The step is allowed if its median cost is at most **2%** above the median at the top.
  Otherwise it is refused and not tried again for 900 decisions. The bowl may move the ceiling only between the top and
  the deepest allowed step. Where no step passes, the ceiling stays at the top and the card runs as it does alone. Every
  trial and every judgement is in the audit (`verdict`, `verdict_state`, `verdict_deepest_step`).
- **One law, no profiles.** The service and batch profiles are removed. The law is: down gain 0.0125, the bowl's center
  0.4, the speed floor at the card's own busy clock, and the verdict's allowance of 2%. The batch profile paced past the
  2% allowance, so it is gone.
- **Why 2%** (the card model, 20 paired seeds):
  - an allowance of 0 leaves the card native on every workload, because every clock step down adds some time to a
    request, and saves nothing;
  - 2% is the smallest allowance that saves energy, and it is below what a person or a service contract can notice.
- **A second workload, AI token generation** (`tools/gpu_workload.py --kind decode`): fp16 matrix-times-vector over
  1 GiB of weights per pass, batch one, so each pass streams every weight from memory, as token generation does. It runs
  as a second confirmation of the same design (10 repetitions × 3 arms × 600 s) after the compute-bound one
  (`scripts/gpu_rented_run.sh`; `SKIP_DECODE=1` skips it). It is labelled by the same rule and reported as its own
  result, never pooled.
- **Every comparison is a base alone against the same base with Omni on top.** The model's report
  (`tools/run_gpu_card.py`) runs two bases:
  - the card's own firmware, alone and with Omni on top;
  - an operator's fixed 105 W power cap, alone and with Omni on top.

  The old one-wire governor is removed as an arm (it was Omni's own earlier version).
- **On the modelled card, before any trial** (`results/sim/gpu_two_wire/`, firmware alone against firmware with Omni on
  top; tuning seeds 5000-5009, fresh seeds 5100-5109):
  - compute-bound work: work per energy +0.70% (tuning) and +0.48% (fresh); median +1.56% and +1.47%; p95, p99 and
    time over the line unchanged within their intervals;
  - AI token generation: work per energy +3.36% and +3.86%; median +0.55% and +0.70%; p95 +0.29% and +0.26%; time over
    the line 0.

  That is a model; the next trial is the card's own meter.

## Amendment 9 (2026-10-03, before any trial on this code)

Everything in amendment 8 stands. Four additions, each run by `scripts/gpu_rented_run.sh` after the two confirmations
and each reported as its own result:

1. **Steady under the limit** (`omni_controller/gpu_bowl.py`, the same in `realms/gpu_card.py`). While the card is
   saturated against its own power limit (work waiting, the draw at 97% of the limit or more), the firmware boosts a
   step, hits the limit and is knocked back. The ceiling is then held at the card's own busy clock under that limit,
   so the same watts serve the work without the knock-backs. It is never held under that clock, the lid stays at the
   start limit, and a blind feed still fails up. In the card model, fully loaded under a fixed cap, this gives about
   +0.6% requests served from the same watts, with p95 about 2% faster.
2. **An operator's power cap underneath.** The card's limit is set to the envelope's lowest watts (70% of its default)
   before the run, and the paired bench runs native (the cap alone), watch and Omni-Compass on top of the cap (the lid
   never above the cap). It runs twice, 5 repetitions × 3 arms × 300 s each time:
   - at the usual load;
   - fully loaded (arrivals at 130% of the card's capacity under the cap), so the result is requests served from the same watts.

   The card is returned to its default limit afterwards.
3. **The GPU fault drill** (`scripts/gpu_fault_drill.sh`). With the request stream running:
   - the governor is killed outright, and the watchdog must hand the card back;
   - the master switch is pulled, and the governor must hand back, exit and refuse to restart while OFF;
   - the response feed is paused, and the governor must fail up.

   Every check must pass, and the card must end at its start limit.
4. **Real AI serving** (`scripts/gpu_vllm.sh`, `tools/llm_workload.py`). An open language model
   (Qwen/Qwen2.5-0.5B-Instruct) is served by vLLM, installed in its own environment. It is asked the same seeded stream
   of prompts in every arm, each for exactly 128 new tokens; 5 repetitions × 3 arms × 300 s. Tokens per second and
   tokens per kilojoule follow from requests served. If vLLM cannot be installed or started on the machine, the stage
   says so and nothing measured before it changes.

## Amendment 10 (2026-10-03, before any trial on several cards)

Everything in amendments 8 and 9 stands. **Several cards in one server** (`scripts/gpu_8card.sh`): every card runs
`scripts/gpu_rented_run.sh` at the same time, each on its own card with its own wire check, envelope, smoke, the two
confirmations and the power cap underneath, on the same committed code. Card i starts its arm rotation i steps later
(`ROT_OFFSET`), so no arm always meets the same neighbours. Each repetition stays paired within its own card (its three
arms on one card); the pooled table per workload holds every card's repetitions (card c, repetition r is pooled as
repetition 100(c+1)+r) and is labelled by the same rule. Each card's own table is reported beside it; a card whose
table is invalid is reported, never dropped. The fault drill runs once, on the first card, after every card has
finished. Last, **one model across every card** (`scripts/gpu_vllm.sh` with GPU = every card): vLLM tensor parallel,
Qwen/Qwen2.5-7B-Instruct, one governor per card on its own card's two wires, all reading the same response times;
the energy is every card's summed; 5 repetitions × 3 arms × 300 s, labelled by the same rule. Each card's energy is read from that card alone (the bench's sampling filtered to the card in each
repetition's own receipt).

**The short design** (`FAST=1`, written before any trial on several cards): each card runs one smoke round and 3
repetitions of the compute confirmation (24 paired repetitions on 8 cards, pooled and labelled by the same rule, each
card's own table reported beside it), then one model across every card with 3 repetitions. AI token generation and the
power cap underneath are measured on the one-card machine (amendment 9) and are not repeated here.

**The whole stacks with a real card inside, on several cards** (written before any trial): `tools/run_hil.py` as on the
one-card machine (amendment 9, the six organisms at 1x, 10x, 100x and 1,000x, repetitions 3, 3, 2, 1 by size, the
adaptive step), each organism on its own card at the same time (organism i on card i; with fewer cards than
organisms, the next organism waits for a card). Each organism's receipt is its own; nothing is pooled across organisms.

**The pooled design** (`POOLED=1`, written before any trial on several cards): every stage of the whole design, with
the repetitions pooled across the cards. Each card runs one smoke round; 3 repetitions of the compute confirmation and
3 of the AI token generation confirmation (24 paired repetitions per test on 8 cards, pooled and labelled by the same
rule, each card's own table beside it); 2 repetitions of each power cap load (16 per load); the six organisms with the
card inside, one repetition per size, each organism on its own card; then one model across every card, 3 repetitions;
the fault drill once. Arm durations are those of the whole design.
