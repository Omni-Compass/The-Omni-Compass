# Review of OmniCompass_FULL_HARNESS.zip (Grok build), 27 September 2026

## What it is
The zip holds 209 files. It combines:
- this repository at commit 1e0f4c3 (older than the current branch);
- parts of the ChatGPT release (`grandmaster.py`, `hardware/cpufreq.py`, `omnicompass/dcgm.py`, `connectors.py`,
  `k8s_controlplane/gpu_vessel.py`);
- Grok's own notes.

Its engine files carry the same SHA as ours, and its C++ is byte-identical to that older commit. Its shield is the
older one, which still has the two bugs the property test found.

## The one real finding: GPU arms B and C collapsed in `hardware/plant.py`
**The bug.** The vendor default on a GPU is always TDP (setting 1). Arm B was `min(native, cap) = cap`, and arm C
was `cap`, so the two gave the same number on every GPU tick. The hardware tables therefore never tested
Omni-Compass-alone on GPUs as a separate arm. Grok found this and it is correct.

**Grok's fix.** C sizes the power limit from the device's own performance law,
`s = (want / rho)^(1/gamma)`, with gamma measured from MLPerf. On CPU it also removed the engine's cap from C.

**Head to head.** All three versions of C ran on the same scenarios:
- development: seed 515151, 24 scenarios per vessel;
- held-out: seed 626262, 48 scenarios per vessel.

Tables: `GROK_HARDWARE_HEADTOHEAD_DEV.txt`, `GROK_HARDWARE_HEADTOHEAD_HELDOUT.txt`.

| Held-out, GPU median gamma | Native | C before | C Grok | C unified (adopted) |
|---|---:|---:|---:|---:|
| Energy (kWh) | 142.26 | 119.34 | 105.97 | **101.87** |
| Work | 174.64 | 174.63 | 174.64 | 174.63 |
| Heat over limit (min) | 22.31 | 6.17 | 17.92 | **5.71** |
| Peak (kW) | 38.44 | 37.64 | 36.90 | **36.72** |
| SLO breach (min) | 0 | 0.04 | 0 | 0.04 |
| Setting changes | 0 | 19.8 | 90.2 | 77.6 |

**Grok's version, GPU.** It saves energy but loses the engine's heat reflex, so its heat-over minutes are about 3
times the unified law's.

**Grok's version, CPU.** It is worse than before:
- energy is within 0.3% of native;
- heat-over minutes are back at native, where the unified law has about one third.

**Adopted: the unified law.**
`s = min(engine cap, (want / rho)^(1/gamma))`, with gamma = 1 for CPU clocks and the MLPerf gamma for GPU power limits.

- It is one derived law for both device kinds. With gamma = 1 it is exactly the earlier CPU law, so the CPU results
  are unchanged.
- The sizing term is Grok's. The cap is the engine's power and heat reflex.

**Held-out result on GPUs** (unified law, against native):
- energy 27-33% lower for the same work (95% interval excludes 0);
- heat-over minutes 73-78% lower;
- peak power lower.

**Against Grok's version on GPUs:**
- energy 3.5-5% lower;
- heat-over minutes 66-72% lower;
- peak power lower in two of three calibrations. In the least-favourable calibration Grok's is 0.07 kW lower.

**Costs, stated:**
- one to two SLO breach-minutes in total over 48 scenarios (Grok's has 0);
- p95 latency +0.3-0.7%;
- more power-limit writes than before. These are register writes, not machine boots.

**Integrity test** (`tests/test_hardware_plant.py`, in `verify.py`):
- GPU arms B and C must differ;
- C must follow the sizing law;
- C does the same work as native and has no more heat-over minutes, on every vessel.

## Not adopted
- **Grok's rightsize SLO rule.** This repository already has it: no shrink while the SLO is breached or without
  nervous-system contraction authority.
- **Grok's CPUFreq wiring.** It is the ChatGPT connector wired without the schedutil floor or the nervous-system
  envelope. This repository's wiring has both.
- **`grandmaster.py`, `connectors.py`, `dcgm.py`, `gpu_vessel.py`.** These are launchers, named interfaces and
  labelled models. None has a live path: each returns "no nv-hostengine" or refuses the push.
