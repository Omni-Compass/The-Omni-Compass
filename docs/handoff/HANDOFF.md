# Omni-Compass: hand-off for the next build

## Contents

| File | What it is | SHA-256 (first 16) |
|---|---|---|
| `OmniCompass.zip` | Latest verified package: 171 files, `python verify.py --full-replay` 74/74 PASS | 5a546370ca1ffac0 |
| `external/OmniCompass_combined.zip` | Second harness author's tree: an older copy of the package plus `k8s_controlplane/`, `k8s_fleet/`, `omnicompass/pools.py`, LIMITS.md, NOTICE, GITHUB.md | as uploaded |
| `mathematics/omni_compass_engine_source_c527df2d.py` | The authenticated engine source (the package's `reference/` holds the same program with comments stripped) | c527df2d3d217a62 |
| `mathematics/OmniCompass_Mathematical_Closed_Structure.pdf` | 140-page prospectus: three-summand carrier, inheritance criterion, stability theorems | 2f5e9214a4625345 |
| `mathematics/equation_form_and_symbol_chart.png` | The printed equation form (1)-(8) and symbol chart | |
| `mathematics/unified_circle_principle.png` | Admissibility, invariance, Lyapunov decrease, convergence to M* | |
| `OMNI_COMPASS_DOMAIN_MAP.md` | Every muscle Omni-Compass can sit on, fit and wiring status | |

## Where things stand (verified)

- Engine: Python and C++ match the authenticated engine exactly; 200 million soak decisions, 0 failures.
- Governor modes: power_protect, throughput, fleet, fleet_balanced, fleet_wear; C++ parity with negative controls.
- Shield (I1-I5), HPA law and savings projector: C++ parity with negative controls. Three independent HPA implementations agree on every step once the upstream exclusive window is used.
- Stack benchmark: pre-registered, 1,000 held-out scenarios, full byte-identical replay.
- Fleet harness (15 s control plane, five vessels, 150 held-out scenarios): the governor as node-pool authority in place of the Cluster Autoscaler (HPA retained) uses significantly less energy than HPA+CA and HPA+Karpenter-lite in every vessel; more node reversals than CA, fewer than Karpenter.
- Recorded PlanetLab shapes (declared scale mapping): energy -40.6% vs HPA+CA, -21.7% vs Karpenter-lite; time healthy -0.08 points.
- Live controller (observe, target, nodepool; dry-run; kill switch restoring from annotations; audit log), capture script, capture replay, pilot scorer and end-to-end self-pilot. At the default headroom of 50%: energy -7.7% and node-hours -13.8% per core-hour, pending-pod time not significantly different from HPA+CA; HPA shortfall about +1.2 minutes per hour (cause open). Never run on a real cluster.

## Open findings to resolve first

1. **Two engine configurations.** The engine ships with `GRANDMASTER_SYMMETRIC_CORE = True` (double-well U: mu U(1-U^2) - (dE/dt)/E_max - lambda_U U), `SPINOR_CLOSURE_ENABLED = True`, U_t = 0.5, and I_U damping lambda_I. The printed chart is the other configuration: U logistic alpha(1-U) - (dE/dt)/E_max - kU(1-U), no spinor factor, general target U_t, no lambda_I term. Every package result uses the symmetric configuration; the printed form has not been wired or benchmarked. The package manual wrongly states that alpha_U and k do not enter equations (1)-(8); they do in the printed form.
2. **Karpenter + VPA.** In the external `k8s_fleet` harness (8 fresh scenarios, same governor code), HPA+Karpenter-lite+VPA-lite used 0.874 kWh vs omni_full 0.922 (about 5% lower), with 110 vs 57 node starts and time healthy 99.5% vs 99.9%. Omni there right-sizes requests only for workloads at minimum replicas. Engine-evolution ablation in that harness: 0.922 to 2.623 kWh, strong causal evidence for the engine.
3. **Inheritance criterion not yet applied.** Connectors use a hand-weighted assimilation blend, with no explicit embedding or left retraction, and the intertwining residual has never been measured (Closed Structure, Definition 11.1, Theorems 11.2 and 11.13).
4. **Stability proof open.** An interval-arithmetic proof on the symmetric core did not close (cubic U term). Candidate routes: the Unified Circle Principle (inward condition on a region, a Lyapunov function, LaSalle) on the printed logistic form; Theorem 5.6 of the Closed Structure (global asymptotic stability iff lambda_M + a_S > 0 and lambda_M a_S + kappa^2 > 0), if its Piece I core in (M, S, b) maps onto the engine's states.
5. The external `k8s_controlplane/hpa_independent.py` and `hpa.py` keep `t >= cutoff`; upstream is exclusive (`t > cutoff`).

## Next build, in order

1. Merge: the latest package as base; add `k8s_controlplane/` and `k8s_fleet/` (with the exclusive-window fix), `pools.py`, LIMITS.md and NOTICE; all their tests inside `verify.py`.
2. The printed field as a named engine configuration (symmetric core off, spinor off, U_t declared, lambda_I = 0), run through every harness beside the symmetric core; correct the manual.
3. Connectors rebuilt to the inheritance criterion: explicit embedding and retraction per muscle; intertwining residual reported on every benchmark.
4. Stability: map the Closed Structure's Piece I core to the engine; attempt the Unified Circle proof on the printed form.
5. Full request right-sizing (all workloads, shield-bounded, restarts counted as wear) in the fleet harness and the live controller; engine-driven headroom in place of the fixed 50%; investigate the HPA shortfall.
6. Rematch against HPA + Karpenter-lite + VPA-lite on fresh held-out scenarios with confidence intervals.
7. Then connectors in the domain-map order: GPUs, cooling, energy supply, job queues.

Rules carried forward: development seeds only for tuning; freeze and fingerprint before held-out runs; amendments recorded; no claim beyond what the verifier reproduces.
