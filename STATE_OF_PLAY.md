# Omni-Compass: state of play, 27 September 2026 (read this first)

This is the whole repository at the commit named in `STATE_OF_PLAY_COMMIT.txt`. Everything below can be rerun from it.

**Rerun the whole thing:** `pip install -r requirements.txt && python verify.py`. It must end
`VERIFICATION: PASS`, and it does at this commit.

## Best measured results, and where each one comes from

| Claim | Evidence | Where |
|---|---|---|
| **B (Omni on top of each platform):** 0 losing cells on held-out scenarios; strictly better on 27 of 28 platform-workload pairs | simulation, pre-registered | `tuning/B_FIX.json`, `tuning/B_TONE_HELDOUT.json` |
| **Four-cluster sites:** B 0 losses on all 7 platforms; C 0 losses vs GKE, AKS/Karpenter, CAST AI, Spot | simulation, held-out | `tuning/SITE_LEAGUE.json` |
| **C (Omni alone), one global setting, 400 never-used scenarios:** 153 better / 174 equal / 37 worse of 364 cells (Holm-corrected) | simulation, confirmatory | `tuning/CONFIRMATORY.json` |
| **C with nervous-system coordination, 400 fresh scenarios:** 151 / 173 / 40 | simulation, confirmatory | `tuning/CONFIRMATORY_COORD.json` |
| **Controllers fighting each other:** lowest of all 8 systems on web (0.07 per day) and four-cluster sites (0.56 per day) | simulation, confirmatory | same file |
| **Real demand, 1,052 recorded PlanetLab machines:** 0 losing cells of 91 | simulation on real traces | `tuning/PLANETLAB_LEAGUE.json` |
| **Faults** (machines dying, spikes, crash loops, noisy neighbours): fewest pages to a human, fastest recovery | simulation, 500 runs per workload | `results/protocol/` |
| **GPU power law** (engine cap over the MLPerf-measured performance law), against native at equal work: energy -27% to -33%, time over the heat limit -73% to -78% | simulation, held-out | `results/hardware/SUMMARY_HELDOUT.json` |
| **Live levers under the nervous system:** 19 of 19 checks on real Kubernetes; kill switch restores everything | live, kind | `results/live/LIVE_LEVERS_2_NERVOUS.txt` |
| **Shadow pilot kit:** a read-only identity made 0 writes across 40 decisions | live, kind | `results/live/LIVE_SHADOW_1.txt` |
| **Safety shield:** 2,000,000 adversarial cases, 0 violations (the test found 2 real bugs, both fixed); C++ twin matches | test | `tests/test_shield_properties.py` |
| **C++ engine:** 100,000,000 decisions, no failures, about 2.3 µs per decision | test | `results/SOAK.json` |

## What still loses, measured

- **C, typical response time, web and four-cluster:** about 20% slower than every platform. Omni fills pods to 80%,
  where the others stop at 70%, and trades response time for energy.
- **C, machine starts and stops:** loses to plain Kubernetes and OpenShift, which hold machines steady and pay for it
  in machine-hours.
- **C, GPU and batch:** energy 1-2% worse and power and heat margins 1-4% worse than the tight packers (AKS/Karpenter,
  CAST AI, Spot).
- **Live, set 3, with a working probe:**
  - Omni kept all 6 machines. Latency near the 500 ms SLO blocks machine release.
  - There is no significant difference from native on anything else, except that C has more waiting pods.
  - The earlier live machine savings (sets 1-2) are withdrawn, because the broken probe had blinded the latency sense
    (`results/live/LIVE_REPS_PROBE_DEFECT.md`).
  - Set 4 prints the decision trail, to show which gate held.
- **A bound, not a loss:** no controller, even one with perfect foresight, can match both the tightest packer's
  machine-hours and the calmest autoscaler's churn at once (`tuning/bound.py`).

## What came from the other AI builds, and what was tested

- **ChatGPT** (`results/external_review/CHATGPT_RELEASE_REVIEW.md`):
  - Its recovery reflex overrides the power envelope. Head to head, this engine is better on 11 gauges in its default
    mode and its reflex on 1. Not adopted.
  - Its CPU-frequency connector was adopted, wired under the nervous system with a schedutil floor and exact restore.
- **Grok** (`results/external_review/GROK_HARNESS_REVIEW.md`):
  - It found that the GPU arms B and C were collapsed in the hardware plant. That is a real bug.
  - The fix was combined with the engine cap into one law, which beats both versions.

## Map

| Path | What it is |
|---|---|
| `omnicompass/core.py`, `cpp/` | six-state engine; C++ twin |
| `omnicompass/closure.py` | closure law: forward projection, boundary correction, turning point, muscle tone |
| `omnicompass/nervous_system.py` | one engine state grants each organ its authority and envelope |
| `omnicompass/shield.py` | safety shield, downstream of everything |
| `omni_controller/` | live Kubernetes controller and levers |
| `fleet/`, `hardware/` | simulation plants |
| `tuning/` | benchmarks, pre-registrations, results |
| `results/live/` | every live run, including the failed and withdrawn ones |
| `docs/OMNICOMPASS_BUYER_EDITION.md` | the buyer-facing report |
| `docs/CONSENSUS_AUDIT.md` | the five-reviewer audit (written by the same assistant that built the code; internal, not independent) |
