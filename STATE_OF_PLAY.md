# Omni-Compass: state of play (read this first)

Current facts only. Earlier states, failures and chronology are kept whole in `docs/HISTORY.md`. The release this page
describes is identified by `RELEASE_MANIFEST.json` (commit, fingerprints of the engine, the C++ twins, the GPU protocol,
the live evidence and the verification receipt), which `verify.py` checks against the files.

**Rerun everything:** `pip install -r requirements.txt && python verify.py` ends with `VERIFICATION: PASS`.

## In one paragraph

Omni-Compass is a supervisory governor that sits on top of Kubernetes and hardware. On a real Kubernetes control plane
it measurably makes services answer faster, with fewer replicas and a clean kill switch. It has **not** yet been shown to
save energy on real hardware: on kind every machine stays powered and energy is a declared model, and the GPU bench that
measures real joules is built and tested but has not been run on a card. That run is the next decisive step.

## Measured on real systems: the newest set, Omni-Compass against Kubernetes as it runs today

Set 21 (`results/live/LIVE_REPS_21.md`): 10 paired repetitions on real Kubernetes (kind), each pair on one machine,
Kubernetes with its autoscaler alone against the same Kubernetes with Omni-Compass on top.

| Result | Kubernetes alone | With Omni-Compass | Change (95% interval) |
|---|---:|---:|---|
| **Response time, 95th percentile** | 304.9 ms | 191.4 ms | **−37%** (proven) |
| Response time, 99th percentile | 438.1 ms | 298.7 ms | −32% (proven) |
| Response time, mean | 151.9 ms | 107.5 ms | −29% (proven) |
| Failed requests | 0 | 0 | equal |
| Replicas, mean | 8.94 | 7.84 | −12% (proven) |
| Machines in service, mean (all stayed powered) | 6 | 4.75 | −21% (proven) |
| CPU used by the service | 0.91 cores | 1.15 cores | +26% (proven): more requests were served, see below |
| Requests served (estimated from response times) | | | **+28%** (+22% to +35%) |
| Energy per request (the model row below ÷ estimated requests) | | | about **−21%** (a model and an estimate) |
| **Energy, parked machines still on at idle power** (declared model, no meter) | 159 Wh | 161.9 Wh | **+1.8%, worse** (proven) |

- **More work was served.** The load is closed-loop (each generator waits for its answer before sending the next), so
  faster answers bring more requests: an estimated 28% more requests were served with Omni-Compass, at about the same
  CPU per request, so the CPU and energy rows compare unequal work. The next set runs a fixed-rate load so the work is
  equal and work per energy is measured directly rather than estimated.
- **No energy saving is shown on kind.** Every machine stays powered; energy is a declared model. The kill switch
  restored every setting in every run; watch mode writes nothing.

## Built and tested, not yet run on real hardware

| Instrument | State |
|---|---|
| **GPU bench** (`scripts/gpu_paired.sh`, native / watch / Omni, the device's own meter, optional wall plug and RAPL, freeze and preregistration) | ready; tested against a stand-in `nvidia-smi` in `verify.py`; **no card has run it** (`results/gpu/` holds models only) |
| CPU clock and GPU power connectors in the controller | built; not run on owned hardware |

## Simulated (models: they show the mechanism, not a measurement)

| Result | Where |
|---|---|
| GPU governor with share floor and busy gate, MLPerf-calibrated card: +5.1% and +1.3% work per kJ, p95 within +10% | `results/gpu/sim/after` |
| Speed lock (speed won elsewhere spent on GPU watts) | `results/gpu/sim/pipeline/` |
| CPU and GPU on one conserved power budget: +1.4% to +5.7% work served against a fixed cap, never over the budget | `results/hardware/NODE_EXCHANGE_*.json`, `docs/CONVEYANCE_LAW.md` |
| GPU groups sharing a site budget: 0 minutes over the budget | `results/hardware/SITE_EXCHANGE_HELDOUT_*.json` |
| Platform leagues, faults, PlanetLab traces, stack benchmark | `tuning/`, `results/protocol/`, `results/` (see `docs/BENCHMARK_REPORT.md`) |

## Verified in code

| Property | Where |
|---|---|
| The canonical engine is `symmetric_verified`; the printed chart is a named variant, not benchmarked | `docs/CANONICAL_ENGINE.md` |
| Nine laws twinned in C++20 and proven equal to the Python; sealed by fingerprint | `results/SEAL.json`, `tools/seal.py` |
| The conveyance law conserves its budget and converges (proof and 20,000 random systems) | `docs/CONVEYANCE_LAW.md`, `tests/test_conveyance.py` |
| Safety shield: 2,000,000 adversarial cases, 0 violations; C++ engine: 100,000,000 decisions, no failures | `tests/test_shield_properties.py`, `results/SOAK.json` |

## Open

1. **The first real-hardware run:** `sudo PHASE=smoke bash scripts/gpu_paired.sh` on a rented NVIDIA machine
   (`docs/GPU_RUN_GUIDE.md`), then `PHASE=confirm` (10 preregistered repetitions). Then a second machine of the same
   type, then another GPU type.
2. **Work per energy on kind:** count requests served, or run an open-loop load at a fixed rate, so work per energy can
   be stated instead of estimated (set 22, `LOADGEN=open`).
3. **CPU and GPU on one power budget on hardware:** the law is simulated; the live exchange is not wired.
4. **A global stability proof** of the forced six-state system (`docs/FORMAL_STATUS.md`).
5. **The principal embodiment for filings** (`docs/CANONICAL_ENGINE.md`, section 5): a decision for the company.

## Where things are

| Path | What it is |
|---|---|
| `docs/INTEGRATION_MANUAL.md` | the manual in the box: wiring it in yourself, stack by stack |
| `docs/METRICS_CATALOG.md` | every gauge, and whether it is measured or modelled |
| `docs/COMPARISON.md` | against Kubernetes, OpenShift, Turbonomic, Borg, Twine and others |
| `docs/CANONICAL_ENGINE.md` | the one engine the software runs |
| `omnicompass/`, `cpp/` | the engine and its laws; the C++20 twins |
| `omni_controller/` | the Kubernetes controller, the GPU governor, the muscles |
| `results/live/` | every live run, including failed and withdrawn ones |
| `docs/HISTORY.md` | earlier states of play |
