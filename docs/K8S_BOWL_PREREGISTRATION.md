# Preregistration: the bowl law on real Kubernetes (set 26)

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

Written and committed before the run. The run's commit is the one that carries this file; nothing in the law, the
harness or this rule changes after it starts.

## What is run

Workflow `benchmark-reps` on `main`, 10 repetitions. Each repetition runs three arms back to back on the same runner,
each on a fresh six-worker kind cluster, in an order rotated by repetition (`scripts/kind_paired.sh`):

| Arm | What governs |
|---|---|
| native | Kubernetes alone (HPA at target 50, scheduler); Omni-Compass not started |
| omni | Omni-Compass on top with the engine's allocation law (`--law governor`, the law of sets 22 to 25) |
| bowl | Omni-Compass on top with the bowl law (`--law bowl`, `omni_controller/controller.py`) |

Load: fixed rate (`loadgen=open`), the same work in every arm. 900 measured seconds per arm. SLO 500 ms at the 95th
percentile. Every Omni arm runs the six-state engine on every decision, the nervous system's authority and release
gate, the shield, the compass, and ends with the kill switch, which must return the HPA target, its replica range,
the pods' CPU limits and every worker to native, with no record left (`scripts/kind_bench.sh`).

## The bowl law in the live controller

The service position is the 95th-percentile response time over the SLO (0 calm, 1 the line); a blind probe or a pod
waiting for a place reads as past the wall. The force is `A tanh((K_P (p - 0.5) + K_D v) / A)` with K_D for critical
damping times the realm push factor 3, the same law and gains as on every realm muscle (`realms/bowl_arm.py`):
up gain 0.10, down gain 0.02, release threshold -0.2. Two levers:

1. **HPA target**, cover from 60% of the operator's target to the operator's own: the up force lowers it (more pods),
   the down force returns it toward the operator's. It is never tighter than native.
2. **Node pool**: past the 0.95 wall one machine more at once; one machine back only while the force is below -0.2,
   the position is below the center, and the nervous system's release gate is open.

## Outcomes and the rule

Primary: **worker nodes in service** (mean) and **95th-percentile response time**, each arm against native, paired
over the 10 repetitions with a t-based 95% interval (`tools/live_reps.py`).

Band first: the bowl arm is a win only if its p95 is not worse than native's (the upper end of the 95% interval of the
paired difference at or under 0) **and** failed requests are not higher. If that holds and machines in service fall
with an interval wholly below 0, the label is **better on machines within the band**. If machines fall but the band
condition fails, the label is **tradeoff**. Otherwise **not established**.

Secondary, reported, not used for the label: p99, mean response time, HPA replicas, pods started, pod start wait, CPU
including Omni-Compass's own, the declared energy models. The omni arm is reported against native and against the
bowl arm by the same rule. A run that fails its own checks (kill switch, controller stopped early, missing permission)
is marked invalid and left out, never silently counted.

Evidence class **L**: real Kubernetes software on kind. Energy on kind is a declared model, not a meter.

## Set 26 result

Bowl arm against native: machines in service -17.2% (-26.4% to -7.9% of native), p95 -64.8%, failed requests 0 on
both: **better on machines within the band** (`results/live/LIVE_REPS_26.md`). The allocation law in the same set:
machines -35.8%, p95 -55.4%.

## Set 27 (written before the run)

The bowl in the live controller now reads the service as the GPU bowl does (`omni_controller/gpu_bowl.py`, GPU
amendments 6 and 7): the mean response time of the latency window between the bare service time (a tenth of the SLO)
and the SLO, held at the bowl's center 0.4 (the GPU service profile); p95 at or past the SLO, a blind probe or a pod
waiting for a place is past the wall. Everything else, the arms (native, omni, bowl), the load, the duration, the
outcomes and the labelling rule above, is unchanged. The run's commit is the one that carries this section.

## Set 27 result

Bowl arm, aligned with the GPU governor, against native: machines in service -15.9% (-1.462 to -0.450 machines),
p95 -65.5% (-311.8 to -156.1 ms), p99 -72.6%, failed requests 0 on both: **better on machines within the band**
(`results/live/LIVE_REPS_27.md`, run 37071353971, commit `d46c959`). The allocation law in the same set: machines
-36.6%, p95 -53.1%.

## The verdict in the live controller (2026-10-03, before any further set)

The bowl law gives a machine back only where it measures that the service is no worse for it
(`omnicompass/verdict.py`, stepwise, in `omni_controller/controller.py`). While the service is calm (inside the bowl,
no pod waiting, no breach), one more machine is given back on trial. The response times of 200 requests served without
it are set against 200 served just before and against the cluster as it first ran on its own:
- at most 2% slower than both: the machine stays given back;
- slower than that: it is taken back and not tried again for 120 decisions.

Where no machine passes, the pool stays as the cluster runs it alone. The HPA target's cover is unchanged: from 60% of
the operator's target up to the operator's own, never looser than native. Every trial is in the audit. The next set
runs with this verdict; sets 26 and 27 ran before it and stay as they ran.

## Set 28 and set 29 (2026-10-03, set 29 written before its run)

Set 28 (run 37087620193, commit `24666d7`) ran the bowl law with the verdict. With Omni-Compass on top against native:
- machines in service −4.7%;
- p95 −65.3%, p99 −68.6%;
- pods waiting 0;
- failed requests 0.

Total CPU including Omni-Compass's own came out **+2.2%** (+0.003 to +0.042 cores), more than the 2% the one rule
allows (`DISCLOSURES.md`, section 3). The cause is the controller's own cost: 0.063 cores, mostly a new kubectl process
for every read, about 20 a minute. The bowl law with the verdict freed only 0.040 cores of work. The allocation law in
the same set: machines −29.6%, p95 −58.0%, total CPU including its own −1.2% (not significant). Set 28's receipt is
`results/live/LIVE_REPS_28.md`, published with this section.

**Set 29** runs the same arms, load, duration, outcomes and rule as set 28. One thing changes: the controller reads
through one `kubectl proxy` started once, under the same least-privilege identity, so a read is a local HTTP request
instead of a new kubectl process (`omni_controller/controller.py`, `Kube`; writes are unchanged; `tests/test_api_proxy.py`).
The label also requires total CPU including Omni-Compass's own to be no more than 2% above native.

Set 29 result (run 37094338955, commit `a3721cc`): the bowl law with the verdict, total CPU including its own **−4.7%**
(−0.071 to −0.017 cores), passes; Omni-Compass's own CPU 0.011 cores (set 28: 0.063). Machines −5.1%, p95 −64.4%,
p99 −71.1%, HPA replicas −7.6%, failed requests 0. No measure significantly worse than native in either arm. Receipt:
`results/live/LIVE_REPS_29.md`.

## The cost to match (written before its run)

The question a buyer asks: what would native Kubernetes have to spend to answer as fast as it does with Omni-Compass on
top? Each repetition runs, on the same runner and the same work, in rotated order:
- native (the operator's HPA target 50);
- native tuned harder by its operator, HPA target 40, 30 and 20 (more pods, faster answers), no Omni-Compass (`ARM=native40`, `native30`, `native20` in `scripts/kind_bench.sh`);
- native with Omni-Compass on top, the allocation law (`omni`);
- native with Omni-Compass on top, the bowl law with the verdict (`bowl`).

The report (`tools/live_reps.py`, "The cost to match") lists every arm's p95, p99, HPA replicas, CPU including
Omni-Compass's own, and machines in service. For each Omni-Compass arm it names the cheapest native setting (by CPU)
whose p95 is at or under Omni-Compass's, and that setting's extra replicas, CPU and machines over Omni-Compass. If no
native setting tried reaches it, the report says so and gives the lowest native p95. 10 repetitions, 900 measured
seconds per arm, fixed-rate load.

## The fault test (written before its run)

Health, security and the babysitting a cluster needs, measured. Every arm (native; native with Omni-Compass on top,
the allocation law; native with Omni-Compass on top, the bowl law with the verdict) meets the same four faults at the
same moments (`scripts/kind_faults.sh`, `FAULTS=1`):
1. at 15% of the run, a worker machine dies (its kind container is stopped) and comes back two minutes later;
2. at 35%, traffic triples for two minutes;
3. at 55%, a pod with no CPU limit burns CPU for two minutes;
4. at 75%, the response-time probe goes blind for one minute.

For each fault the report (`tools/live_reps.py`, "The fault test") gives the time to recover (from the fault's start
until responses stay under the line for 30 s straight, at most 300 s) and the share of samples over the line or failed
in the 300 s after it, paired against native over 10 repetitions. All the usual gauges are reported as well, now
including the share of response samples over the line (`pilot/bench_report.py`). Lower is better in each.

**The fault test, first run** (run 37094604580, commit `a149d4e`; `results/live/FAULTS.md`). Omni-Compass on top
recovered faster than native from every fault (allocation law: machine down −29%, runaway pod −35%, spike −7%; bowl
law: −14%, −17%, −6%), p95 −53% and −55%, p99 −27% (not significant) and −57%. One measure was worse: with the bowl law,
**HPA replicas +8.2%** (+0.41 to +0.99, significant), with CPU and machines unchanged and no energy saved, so outside
the one rule (`DISCLOSURES.md`, section 3). The cause: past the wall the bowl lowers the HPA target at once (more pods,
the faster recovery), then handed the operator's target back step by step and held each step for the autoscaler's
window, so the extra pods outlived the fault.

**The change, written before the re-run** (`omni_controller/controller.py`, the bowl's push and pull on the HPA target;
`tests/test_bowl_controller.py`, "fault over"): once the responses are back inside the band (the bowl's position under
its center), the response line is clean and no pod is waiting, the operator's own target returns at once and is not
held by the window. More pods only while the fault lasts. The re-run is the same fault test, arms, load, duration and
rule (set 30 F); set 30 runs the same code without faults, to show nothing else moved.

## The bill on a real cloud (written before its run)

The question a buyer pays for: the same work, a smaller bill? On kind every machine stays powered, so a machine given
back saves only a declared model's energy. On a real cloud the machine is deleted and stops being billed. The run
(`.github/workflows/aks-metered.yml`, `scripts/aks_paired.sh`, `scripts/kind_bench.sh` with `PLATFORM=aks`):

- **The cluster.** Azure Kubernetes Service, a fresh cluster for every arm, built the same way:
  - a system pool of one machine, tainted so no workload lands on it (AKS's add-ons and the load generator: kind's
    control plane);
  - a work pool starting at 4 machines (Standard_D2s_v5) under **Azure's own cluster autoscaler** (min 1, max 4; scale
    down after 2 minutes unneeded), which deletes a machine once it is empty.
- **The arms**, rotated in each repetition:
  - native: Kubernetes with Azure's autoscaler alone;
  - native with Omni-Compass on top, the bowl law with the verdict (`bowl`);
  - native with Omni-Compass on top, the allocation law (`omni`).

  With Omni-Compass on top, the machines it gives back are idled (new pods go elsewhere, their pods leave first), and
  Azure's autoscaler then deletes them. Omni-Compass never deletes a machine itself.
- **The same work** in every arm: the fixed-rate load of sets 22 onward, 900 measured seconds after 120 s of warm-up.
- **The bill.** Every 15 s, the number of work machines that exist (in service or idle, every one is billed),
  integrated over the measured window: billed machine-hours, priced at Azure's list price for the machine
  (USD 0.096 an hour for Standard_D2s_v5, Linux, pay as you go, set in the workflow's input). Omni-Compass never reads
  this count.
- **Outcomes.** Billed machine-hours and the bill (lower is better), and every gauge of sets 28 and 29 (response time,
  failures, pods waiting, CPU including Omni-Compass's own), paired against native with 95% intervals over 5
  repetitions. Labelled by the one rule (`DISCLOSURES.md`, section 3): nothing more than 2% worse, and only where the
  bill or energy is saved.
- **Housekeeping.** One repetition at a time; each cluster deleted when its arm ends, before the next is made; the
  resource group deleted at the end of every repetition whatever happens. It needs the repository secret
  `AZURE_CREDENTIALS`.
