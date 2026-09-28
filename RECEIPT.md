# Omni-Compass: the receipt

Four lines. Each says what kind of evidence it is. Everything else in this repository is detail behind one of them.

| # | Layer | What is established | Class | Number | Where |
|---|---|---|---|---|---|
| 1 | Mathematics | The controller conveys U to its target: proved in continuous time over the declared box; the executed step-by-step controller stays within 0.0315 of the target, inside the 0.10 basin | T, and V for the step constant | 500 / 500 frozen fixtures conveyed and certified; 0 invariance failures in 100 000 steps | `docs/TRACKING_THEOREM.md`, `results/TRACKING_BOUNDS.json` |
| 2 | Simulation | Energy and service against modelled platforms, **with the losses left in** | S | e.g. −40.6% energy vs HPA+Cluster Autoscaler on recorded traces; energy 1–2% worse than tight packers on GPU and batch; machine round trips worse | `docs/EVIDENCE_LEDGER.md`, `docs/CLAIMS_REGISTER.md` |
| 3 | Real Kubernetes | Omni on top of a real control plane (kind), 10 paired repetitions | L | p95 response time −37% (proven); 0 failed requests; kill switch restored every setting; energy is a model there, and the honest row is 1.8% **worse** | `results/live/LIVE_REPS_21.md` |
| 4 | Physical GPU | Successful work per joule measured by the device, Omni against native, with the service guardrails | P | **not yet measured** | `scripts/gpu_paired.sh`, `docs/GPU_PREREGISTRATION.md` |

## Line 4, when it exists

It will be one number with its 95% interval and one label chosen by rule:

- SUPERIOR WITHIN GUARDRAILS;
- ENERGY IMPROVEMENT WITH SERVICE TRADEOFF;
- NONINFERIOR / INCONCLUSIVE;
- NOT ESTABLISHED;
- WORSE;
- NOT ATTRIBUTABLE: WATCH DIFFERS FROM NATIVE;
- INVALID.

It is published only if:

- the watch arm made zero writes and does not differ from native;
- one writer held the limit throughout;
- every arm ended at the snapshot limit;
- the code was frozen and committed before the first trial.

Smoke runs never count.

## What the product is

A small supervisory governor for a GPU node or a small pool, run after the vendor's own limiter.

- **One job:** successful work per joule inside a declared service envelope.
- **One actuator:** the power limit.
- **One writer:** it stops if anything else writes the limit.
- **Fails up:** a blind sensor, a refused write or heat each return the card to full power, or stop tightening.
- **Kill switch:** restores the snapshot and reads it back.

It is not a cluster manager: Kubernetes, Borg and Twine run clusters; Omni governs power inside them.

## Identity

Every number above names the engine that produced it: canonical `symmetric_verified`, mechanism id
`29d9808dfb8f…` (it changes whenever any of its eight parts changes) (`results/MECHANISM_IDENTITY.json`); release fingerprints in `RELEASE_MANIFEST.json`.
