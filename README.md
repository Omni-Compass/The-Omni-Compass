# Omni-Compass

A six-state control engine that governs Kubernetes: Kubernetes stays as the execution layer, Omni-Compass is the single authority above it.

**Read first:** `docs/OMNI_COMPASS_TECHNICAL_MANUAL.pdf`

## License

Free to download, run, modify and build on for simulation, evaluation, testing, research and non-commercial use,
including evaluating it on your own systems. Commercialization or monetization in any form requires a paid license from
The Omni-Compass LLC. Omni-Compass is protected by copyright and by patents and patent applications held by The
Omni-Compass LLC. See `LICENSE`.

## Contents

| Path | What it is |
|---|---|
| `omnicompass/core.py` | The engine: equations (1)–(8), RK4, bounded controller, event predicates |
| `omnicompass/adapter.py` | The stack governor: sense, assimilate, evolve, allocate; observe/autopilot modes; kill switch |
| `omnicompass/shield.py` | Safety shield: invariants I1–I5 enforced before execution |
| `omnicompass/muscles.py` | Infrastructure component catalog with sourced resource footprints; fleet energy model |
| `omnicompass/stack_sim.py` | Synthetic fragmented-stack model, extracted byte-for-byte from the reference engine |
| `cpp/` | C++20 engine core, C++20 governor, soak test (CMake) |
| `benchmarks/stack_benchmark.py` | Stack benchmark: native, observe, autopilot, kill, switch-on, no-dynamics |
| `fleet/` | 15-second Kubernetes control-plane harness: metrics-server, HPA, Cluster Autoscaler, Karpenter-lite, vessels |
| `k8s_controlplane/` | Independent HPA+CA replica, dual HPA (`t > cutoff`), pools, suite scoreboard |
| `omnicompass/pools.py` | elastic / always_on / idle_power actuation |
| `omni_controller/` | Observe / target / nodepool kubectl stub + kill |
| `HARNESS.md` | How to run every bench in this tree |
| `LIMITS.md` | What the numbers are and are not |
| `NERVOUS.md`, `omnicompass/nervous.py` | Nervous-system register: which muscles are wired, sensed or open |
| `pilot/score.py` | Scores your own pilot from your cluster captures, with confidence intervals |
| `pilot/selfpilot.py` | End-to-end self-pilot: the shipped controller against a simulated cluster, captured and scored |
| `scripts/kind_pilot.sh`, `deploy/kind/` | Live pilot on a real Kubernetes control plane (kind) |
| `docker-compose.yml`, `deploy/local/` | Local lab: one command builds a kind cluster on your Docker and runs the live pilot |
| `docs/DOMAIN_MAP.md` | Every muscle Omni-Compass can sit on, with fit and wiring status |
| `docs/handoff/` | Handoff notes, mathematics and engine source |
| `benchmarks/fleet_overhead.py` | Fleet-scale component overhead model |
| `benchmarks/core_evidence.py` | Canonical 500-run population with counterfactuals |
| `results/` | Pre-registration, development run, two 500-scenario held-out runs, core evidence, verification log |
| `reference/` | The reference engine that defines the mechanism, with provenance record |
| `fixtures/` | 500 frozen reference trajectories |
| `tests/` | Parity and provenance tests |
| `tools/` | Program fingerprint and reference-stripping tools |
| `docs/` | Technical manual, claims register, due diligence, pilot protocol, figures and their build scripts |
| `verify.py` | One-command verification |

## Lab: real Kubernetes runs

Two ways to run Omni-Compass on a real Kubernetes control plane (kind: real API server, scheduler, HPA,
metrics-server). Each run does: baseline (HPA alone, Omni observing and writing nothing), Omni in target
mode, kill-switch restore check, then a scored comparison.

| Workflow | Cluster | Omni-Compass drives | Start it |
|---|---|---|---|
| `live-kind` | 1 node | HPA target | Actions → live-kind → Run workflow, or `[kind]` in a commit message |
| `live-kind-full` | 1 control plane + 6 workers | HPA target, node pool (cordon/drain/uncordon), power sensing | Actions → live-kind-full → Run workflow, or `[full]` in a commit message |

Results appear on each run's summary page and as an artifact. Locally (Docker Desktop): `docker compose up --build`
runs `live-kind`; results land in `lab_results/run_<date>/`.

Full-engine run (`scripts/kind_full.sh`): baseline on all workers with Omni observing (must write nothing), then
Omni drives the wired muscles, then the kill switch must restore the HPA target and return every worker to service.
Limits: a parked kind worker is a cordoned, drained container, counted as off; power is a declared model
(`scripts/kind_power.sh`, the same constants `pilot/score.py` uses), not a meter. Energy numbers from kind are modelled.

## Verify

```
pip install -r requirements.txt
python verify.py          # full
python verify.py --quick  # abbreviated
```

## Results on 1,000 held-out scenarios

Seeds 346410161 / 360555127, 500 scenarios each, generated from `results/heldout_seed_*/SUMMARY.json`. The Kubernetes baseline is a documented-behaviour reference model, not the upstream controllers, run at HPA targets 0.5 to 0.8 (manual Section 8.3). Throughput mode applies the same power rules as the reference and is the like-for-like comparison; power-protect additionally enforces the site power limit. With the governor in observe mode, Kubernetes runs bit-identically to Kubernetes alone (500/500 and 500/500).

| | Kubernetes reference (HPA 0.7) | Omni + Kubernetes, power-protect | Omni + Kubernetes, throughput |
|---|---|---|---|
| Energy (kWh) | 168.9 / 169.2 | 132.2 / 132.3 | 121.7 / 121.5 |
| Time healthy | 79.3% / 78.5% | 89.9% / 89.7% | 91.2% / 91.4% |
| Recovery time (min) | 57.2 / 58.4 | 27.9 / 27.2 | 17.8 / 15.2 |
| Scenarios recovered | 91.8% / 91.8% | 96.8% / 97.2% | 99.2% / 100.0% |
| Physical violations (all types) | 13.9% / 14.9% | 8.8% / 9.0% | 7.4% / 7.1% |
| Backlog violations | 2.5% / 2.6% | 6.7% / 7.0% | 1.6% / 1.5% |
| Power-limit violations | 12.8% / 13.8% | 3.5% / 3.7% | 6.9% / 6.5% |
| Heat violations | 8.0% / 8.8% | 0.3% / 0.4% | 2.7% / 2.5% |
| Work completed | 99.82% / 99.97% | 99.63% / 99.83% | 99.98% / 100.00% |
| Contradictory commands per run | 9.6 / 9.4 | 0.0 / 0.0 | 0.0 / 0.0 |
| Invariant violations I1-I5 per run | 9.56 / 9.44 | 0.00 / 0.00 | 2.72 / 2.69 |
| Invariant violations excluding I4 (power) | 6.91 / 6.80 | 0.00 / 0.00 | 0.00 / 0.00 |
| Scale direction reversals (wear) | 2.19 / 2.22 | 3.06 / 3.08 | 1.93 / 1.92 |
| Thermal cycling | 0.75 / 0.75 | 0.59 / 0.59 | 0.63 / 0.63 |
| Machines started | 4.8 / 4.8 | 10.7 / 10.6 | 6.5 / 6.6 |
| Machines stopped | 1.2 / 1.2 | 2.6 / 2.6 | 3.3 / 3.4 |
| Machine round trips (started, later stopped) | 1.1 / 1.1 | 2.6 / 2.6 | 1.7 / 1.8 |

## Fleet harness: 15-second Kubernetes control plane (`fleet/`)

metrics-server, HPA, Cluster Autoscaler and Karpenter-lite at their documented cadence over many workloads per cluster. Five vessels in two families: elastic (web, multi, batch, gpu: nodes may be powered off) and always-on (gpu_always_on: power-off not permitted, idle nodes may only be parked). Omni-Compass is the node-pool and power authority in place of the Cluster Autoscaler (HPA retained), decisions every 60 s, in four settings: energy-first, balanced and wear-first (the equation (2) gate at increasing strength) and park (capacity reductions executed as parking: Ready, 25% of idle power). 30 held-out scenarios per vessel from seed 700000; observe mode bit-identical to HPA + CA in all. Workloads are synthetic.

| Vessel | Setting | Energy vs HPA 0.7 + CA | Energy vs HPA 0.7 + Karpenter-lite | Machines powered off (Omni / CA / Karpenter) | Park moves |
|---|---|---|---|---|---|
| web | energy-first | -34.5% (better) | -16.9% (better) | 10.9 / 7.7 / 13.5 | 0.0 |
| web | balanced | -33.2% (better) | -15.3% (better) | 10.4 / 7.7 / 13.5 | 0.0 |
| web | wear-first | -29.7% (better) | -10.9% (better) | 10.2 / 7.7 / 13.5 | 0.0 |
| web | park | -15.9% (better) | +6.7% (worse) | 0.0 / 7.7 / 13.5 | 14.5 |
| multi | energy-first | -34.3% (better) | -16.6% (better) | 46.3 / 32.4 / 54.0 | 0.0 |
| multi | balanced | -33.0% (better) | -15.0% (better) | 43.7 / 32.4 / 54.0 | 0.0 |
| multi | wear-first | -29.6% (better) | -10.6% (better) | 43.1 / 32.4 / 54.0 | 0.0 |
| multi | park | -15.6% (better) | +7.0% (worse) | 0.0 / 32.4 / 54.0 | 61.8 |
| batch | energy-first | -17.2% (better) | -9.7% (better) | 26.4 / 1.9 / 43.0 | 0.0 |
| batch | balanced | -12.4% (better) | -4.5% (better) | 15.2 / 1.9 / 43.0 | 0.0 |
| batch | wear-first | -12.3% (better) | -4.3% (better) | 13.3 / 1.9 / 43.0 | 0.0 |
| batch | park | -15.3% (better) | -7.7% (better) | 0.0 / 1.9 / 43.0 | 41.7 |
| gpu | energy-first | -4.9% (better) | -2.7% (better) | 8.2 / 4.4 / 23.8 | 0.0 |
| gpu | balanced | -5.0% (better) | -2.8% (better) | 6.3 / 4.4 / 23.8 | 0.0 |
| gpu | wear-first | -4.5% (better) | -2.3% (better) | 4.3 / 4.4 / 23.8 | 0.0 |
| gpu | park | -4.9% (better) | -2.7% (better) | 0.0 / 4.4 / 23.8 | 14.4 |
| gpu_always_on | energy-first | -4.7% (better) | -3.2% (better) | 0.0 / 0.0 / 0.0 | 14.4 |
| gpu_always_on | balanced | -4.7% (better) | -3.2% (better) | 0.0 / 0.0 / 0.0 | 10.9 |
| gpu_always_on | wear-first | -4.2% (better) | -2.8% (better) | 0.0 / 0.0 / 0.0 | 8.0 |
| gpu_always_on | park | -4.7% (better) | -3.2% (better) | 0.0 / 0.0 / 0.0 | 14.4 |

Run: `python -m fleet.benchmark --seeds 30 --seed-base 700000 --out out/` (manual Section 8.8).

Throughput mode does not enforce invariant I4 (projected power); its I4 count is included above. The governor issues no page actions by design, so human pages are not reported as a result. All stack results are for a declared synthetic model, not production systems. See `docs/PILOT_PROTOCOL.md` and `docs/CLAIMS_REGISTER.md`.

## Recorded workloads (PlanetLab)

The frozen laws, without retuning, on recorded utilization shapes from 9 PlanetLab/CoMon VM CPU traces, with a declared scale mapping, governor as node-pool authority in place of the Cluster Autoscaler (30 scenarios; `fleet/traces/`, SHA-256 registered). Observe identical in 30/30.

| Arm | Energy vs HPA 0.7 + CA | vs Karpenter-lite | Time healthy | Node reversals |
|---|---|---|---|---|
| k8s_hpa70_karpenter | -24.2% | +0.0% | 100.00% | 1.93 |
| omni_fleet | -40.6% | -21.7% | 99.92% | 2.03 |
| omni_fleet_balanced | -37.5% | -17.5% | 99.92% | 1.87 |
| omni_fleet_wear | -31.0% | -8.9% | 99.92% | 1.57 |
| omni_fleet_park | +1.3% | +33.6% | 99.92% | 0.00 |

Energy differences of the energy-first, balanced and wear-first settings are significant against both baselines; time healthy and work completed are significantly lower by 0.08 points and 0.01%.

## Savings projection

`python benchmarks/savings.py` (C++: `oc_savings`) applies the measured energy reduction relative to HPA + Karpenter-lite to declared fleet profiles and writes `results/SAVINGS.csv`: annual MWh, USD and t CO2, with low / high bounds from the paired 95% intervals. It is a projection from simulation, not measured savings. Edit `PROFILES` in `benchmarks/savings.py` for your own fleet and prices.

## Running Omni-Compass on your cluster

`omni_controller/` is the live controller. It has been tested against a fake kubectl only; run it observe-first.

```
# 1. observe only (read-only permissions): decisions logged, nothing written
kubectl apply -f deploy/rbac-observe.yaml
python -m omni_controller.controller --mode observe --interval 60 --audit audit.jsonl
# 2. write HPA targets (after reviewing the observe log); try --dry-run first
kubectl apply -f deploy/rbac-target.yaml
python -m omni_controller.controller --mode target --dry-run
python -m omni_controller.controller --mode target
# 3. size one node pool the Cluster Autoscaler does not manage (example: AWS Auto Scaling group)
python -m omni_controller.controller --mode nodepool --min-nodes 3 --max-nodes 40 \
  --node-scale-cmd "aws autoscaling set-desired-capacity --auto-scaling-group-name POOL --desired-capacity {n}"
# kill switch: restores every HPA target Omni changed, returns to observe
touch /tmp/omni.kill
```
In-cluster: `docker build -f deploy/Dockerfile -t omni-compass:local .` then `kubectl apply -f deploy/controller.yaml`.

## Running on real data

No real capture or recorded trace has been run inside this package (no cluster, no network access here). The paths are tested on inputs in the exact real formats:

```
# 1. capture a live cluster (read-only; kubectl + jq)
OUT=capture.csv INTERVAL=15 DURATION=21600 bash fleet/capture/kube_capture.sh
# 2. what Omni-Compass would have recommended (observe only; counterfactual)
python fleet/capture_replay.py capture.csv --idle-w 200 --dyn-w 350 --out replay/
# 3. every fleet arm on recorded PlanetLab workloads
python -m fleet.planetlab --dir fleet/traces/planetlab --scenarios 30 --out planetlab_out/
```
