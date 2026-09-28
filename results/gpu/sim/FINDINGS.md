# GPU governor on the modelled card: what binds, and what was tried

Model only (`tools/gpu_physics_sim.py`, MLPerf-calibrated card shape, 5-10 paired repetitions, gammas 3 and 1.5).

## What decides the power limit (defaults: 2 s decisions, 0.70 share floor, busy gate at 0.5)

One 630 s run, 300 decisions, gamma 3:

| Bound that decided the limit | Decisions |
|---|---:|
| busy gate (smoothed utilisation at or over 0.5): the start limit | 164 |
| share floor (0.70 of the start limit) | 134 |
| response-time reflex | 2 |

The engine requests a cap of 0.650 at every utilisation below 0.6 (median; 0.669 at 0.6-0.8, 1.0 above 0.8). 0.65 is
the lowest power cap the safety shield admits (invariant I2 in `omnicompass/shield.py`, preregistered and frozen).

## Why the single-card gain stays near +5% / +1.3% within the +10% p95 guardrail

- In quiet periods the limit already sits at the floor, within 0.05 of the engine's lowest admissible cap.
- In busy periods the card is at its start limit, and that is where most of the energy is spent. Capping there slows
  the queue: a graded floor under moderate load (0.85-0.90) failed the p95 guardrail on the gamma 1.5 card (+8.3% to
  +12.9%, upper bounds +12% to +18%).
- Larger savings need either the site level (watts moved between GPUs and CPUs under one budget,
  `hardware/node_exchange.py`), or a guarantee stated against the customer's response-time target instead of +10% of
  native (the old governor reached +12.9% work per kJ within the 500 ms target, `results/gpu/sim/before`).

## Tried and not adopted

| Variant | gamma 3: work/kJ, p95 | gamma 1.5: work/kJ, p95 | Verdict |
|---|---|---|---|
| defaults (reference) | +5.2%, +0.8% | +1.3%, +4.0% | kept |
| compass stroke: the start limit in expansion (quadrant I), floor 0.50-0.65 in compression and re-alignment | +4.1%, +0.3% | +1.1%, +3.8% | not adopted: less energy saved; the floors below 0.65 never bind (shield I2) |
| stroke with a 0.75 share floor | +3.5%, +0.5% | +1.0%, +2.3% | not adopted |
| graded mid-load floor 0.85-0.90 | up to +7.1% | fails the guardrail | not adopted |
