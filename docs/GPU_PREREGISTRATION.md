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
- **Repetitions:** 10 in confirmation, each with all three arms back to back, order rotated.
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
  - CPU package energy (RAPL), where present.

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
