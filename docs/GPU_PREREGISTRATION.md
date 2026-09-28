# GPU bench preregistration

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
