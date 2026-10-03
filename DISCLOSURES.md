# Disclosures, Declarations and Disclaimers

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](LICENSE).

This page is the one place every declaration about Omni-Compass is made. The README, the manual, the book, every guide
and every report point here. Where any other page seems to say more than this page, this page governs.

## 1. Rights

1. Omni-Compass, its engine, its mathematics, its software and its documentation are the property of The Omni-Compass
   LLC. Patent applications, copyright registrations and trademark applications covering them have been filed in the
   United States by The Omni-Compass LLC. No filing number is stated here, and no grant, registration or approval is
   claimed.
2. The software is licensed for evaluation and simulation only (`LICENSE`). Running it in production, on any system
   beyond evaluation, or in any product or service, requires a signed, paid Omni-Compass Enterprise License.
3. Names of other companies and products (NVIDIA, Kubernetes, Red Hat OpenShift, Amazon EKS, Google GKE, Microsoft
   AKS, Karpenter, Lambda and others) are the property of their owners. They identify the systems Omni-Compass was
   tested with or connects to. No affiliation, endorsement or certification by any of them is stated or implied.

## 2. What a result is, and what it is not

1. Every result carries its evidence class: **T** a theorem, **V** verified in code, **S** a model (simulation),
   **L** live software (real Kubernetes on GitHub's machines), **P** a physical meter (a real card's own power meter).
   A model is a statement about the model. A software benchmark is a statement about the software and machine it ran
   on. Only a meter speaks for hardware.
2. The models were written by the same people who wrote the law. They show how the mechanism behaves; they are not an
   independent test.
3. On Kubernetes in kind every machine stays powered, so energy there is a declared model, not a meter.
4. Every comparison is paired: the same seed, load and clock with and without Omni-Compass, in an order rotated by
   repetition. Intervals are 95% intervals over the paired repetitions. Ratios across seeds are summarised as geometric
   means. Labels are assigned by code from rules written and committed before the run
   (`docs/GPU_PREREGISTRATION.md`, `docs/REALMS_PREREGISTRATION.md`, `docs/K8S_BOWL_PREREGISTRATION.md`), never by hand.
5. Losses and failed runs are kept beside the wins (`docs/EVIDENCE_LEDGER.md`, `results/live/`, git history). The
   first real-card run, for example, saved energy (+3.6% work per energy, proven) and made the slowest answers 58.5%
   slower; it is published as it happened.
6. No result is a promise of a saving on any other system. No dollar figure in this repository is a measured result.
   Nothing here is a vendor certification, a safety certification, legal advice or investment advice.

## 3. The rule Omni-Compass keeps on every muscle

Omni-Compass sits on top of a muscle that already works and moves its settings only to save energy, and only where it
measures that the muscle loses at most **2%** in any measure: work done, response time (median, p95 or p99), time over
the service line, or the machine's own cost of running Omni-Compass. Where no move passes that test, Omni-Compass leaves
the muscle exactly as it runs alone. On a live system the verdict (`omnicompass/verdict.py`) measures it with paired
trials on the muscle itself before every step. Every result reports each measure, and where one is worse at all, by
however little, the result says so and by how much.

## 4. The wiring declaration

**Omni-Compass acts only through the wires it is given.** It reads the meters it is pointed at and moves the settings
it is allowed to move. If a reading is the wrong one, slow, or blind; if a lever is the wrong one, already owned by
another controller, or given a range (cover) that is wrong for the machine; if a band or a service line is set for a
different workload; then Omni-Compass will do exactly what its law says with the wrong information, and the result will
not be the published one.

Therefore:

1. **It cannot be slapped on.** Every installation goes through the levels of the manual in order (chapter 9), starting
   read-only, and every writing level begins with the wire check (manual, section 8.4) and a watch arm that must equal
   native.
2. **If your paired receipts differ from the published benchmarks in direction** (service worse, or no saving where one
   was shown), **the first presumption is wiring, not the law.** Confirm the installation with the checks in the
   manual's section 8.5 (*Wired right or wired wrong*) before drawing any conclusion about Omni-Compass.
3. **This has happened to us, and is published.** On the first real card (NVIDIA A10, 2026-10-02) the governor read
   being busy as trouble, set its power lid under the card's own working draw and allowed the clock under the card's own
   working clock; the card served bursts more slowly and the slowest answers were 58.5% slower. The cause was found in
   the card's own samples and corrected (`docs/GPU_PREREGISTRATION.md`, amendments 6 and 7). That is what a wiring
   fault looks like, and how it is found.
4. Omni-Compass never writes outside a lever's cover, never fights another writer (it stops and leaves that lever alone),
   reads back every write, and returns every lever to the value it read before its first write when it stops or when the
   OFF switch is used. These protect the machine; they do not make a wrong wiring right.

## 5. Safety and responsibility

1. Run watch mode first; run the wire check before any write; keep the master OFF switch (`python3 tools/omni_switch.py off`, the
   whole harness at once) in reach at every level, and use it at the first sign of anything wrong, a suspected breach included.
2. Omni-Compass is a supervisory governor. The machines' own controls (firmware, autoscalers, safety systems) stay in
   place and keep their own protections; Omni-Compass sets only values they already accept.
3. Do not connect Omni-Compass to safety-critical systems (vehicles, medical devices, grid protection, life safety)
   except as a modelled study, and never without the qualified review those systems require.
4. The software is provided "as is", without warranty of any kind, as stated in `LICENSE`. The operator is responsible
   for its use on their systems.

## 6. Nothing is set in stone

1. The software, the law's settings, the benchmarks, the results, the documents, the licensing terms and this page may
   change at any time, without notice. The version in the repository's `main` branch at a given commit is the version
   that commit describes; `RELEASE_MANIFEST.json` and `python3 verify.py` identify it.
2. Statements about work in progress, planned features, expected results and future runs are expectations, not
   promises. Where a result has not yet been measured, the documents say so (`STATE_OF_PLAY.md`,
   `docs/DOSSIER.md`, section 8).
3. A signed Omni-Compass Enterprise License governs its own terms for its own term.

## 7. Privacy and data

Omni-Compass contains no telemetry. It sends nothing to The Omni-Compass LLC or anyone else, and makes no network
connection of its own except to the systems an operator points it at. Its logs and receipts stay on the operator's
machines.

## 8. Where everything is

| Question | Page |
|---|---|
| What has been measured, and how strongly | `STATE_OF_PLAY.md`, `docs/DOSSIER.md`, `docs/EVIDENCE_LEDGER.md` |
| The rules written before each run | `docs/GPU_PREREGISTRATION.md`, `docs/REALMS_PREREGISTRATION.md`, `docs/K8S_BOWL_PREREGISTRATION.md` |
| How to wire it, level by level, and how to confirm it is wired right | `docs/OMNI_COMPASS_MANUAL.md` (chapters 8 and 9), the book `docs/OMNI_COMPASS_MANUAL.pdf` |
| The license, in plain answers, and third-party components | `LICENSE`, `LICENSING_FAQ.md`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, `PATENTS.md`, `TRADEMARKS.md` |
| The 656 muscles, what each is for and how it is wired | `docs/MUSCLE_CATALOG.md` |
| Proof the code is the code that ran | `python3 verify.py`, `RELEASE_MANIFEST.json`, `results/SEAL.json` |
