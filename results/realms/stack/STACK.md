# The stacked organism: all four realms on one clock, native against Omni

Evidence class **S** (simulation). Commit `fcefbc8d8d11`, seeds 4000-4009, 1226 muscles stacked: the four realm organisms (345 + 262 + 282 + 337), every muscle as often as it appears in them, duplicates included. A duplicate is still a muscle that has to converge. Each realm keeps its own internal coupling (heat into its cooling, load onto its batteries). Preregistered: `docs/REALMS_PREREGISTRATION.md`, round 4.

- **Stacking changes nothing natively:** the stacked native run equals each realm's own native run, plant by plant, on every seed.
- **Kill switch:** every knob handed back under both governor arms on every seed: yes.

| Comparison | Label | Work per energy | Work | Energy | Violations (pp) |
|---|---|---:|---:|---:|---:|
| one governor vs native | **ENERGY IMPROVEMENT WITH SERVICE TRADEOFF** | +0.02% (+0.00 to +0.05) | -0.11% (-0.13 to -0.10) | -0.14% (-0.16 to -0.11) | +1.43 (+1.32 to +1.54) |
| separate governors vs native | **ENERGY IMPROVEMENT WITH SERVICE TRADEOFF** | +0.04% (+0.02 to +0.06) | -0.11% (-0.12 to -0.10) | -0.15% (-0.17 to -0.13) | +1.45 (+1.40 to +1.50) |
| one governor vs separate governors | **WORSE** | -0.02% (-0.02 to -0.01) | -0.00% (-0.01 to +0.01) | +0.01% (-0.00 to +0.03) | -0.02 (-0.14 to +0.10) |

Work is the mean over the stacked muscles of work with Omni over work native; energy is total joules; violations are the change in the share of periods any muscle was out of its service target. Labels by the preregistered rule. These are models, not meters.
