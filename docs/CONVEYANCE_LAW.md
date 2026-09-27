# The conveyance law: moving a conserved budget between organs

## 1. What the manuscript says, read as mechanism

| Source | Text | Mechanism |
|---|---|---|
| Ch. 29 §8 | "E_system = E + U + S + B … dE_system/dt = 0 (over full cycle). Energy redistributes. Energy reorganizes. Energy does not diverge." | The budget (site watts, cluster cores) is **conserved**: it is moved between organs, never created. |
| Ch. 31 §4 | "Redistribution B acts as mediator between the baths. When E grows locally, B increases to distribute gradients." | Budget flows **down the gradient of need**: from organs holding surplus to organs in deficit. |
| Ch. 31 §5 | "eigenvalues of the coupled system must remain bounded … Re(λᵢ) ≤ 0" | The flow must have a proof of convergence, not a tuned damper. |
| Ch. 30 §5-7 | "Redistribution surge … channels stored deviation into expansion … controlled release … No discontinuity." | A **reserve** is held and released **continuously** to organs at their limit. There is no on/off. |
| Ch. 29 §6 | "Backpressure develops through S … Compression is … structured inward rotation." | When need falls, surplus is **pulled back** smoothly. Budget nobody needs is not spent. |
| App. J | "the engine can only act through what you expose" | Organs keep their own mechanisms. The law sets only each organ's share of the budget. |

## 2. The law

**Notation.**
- Organs i = 1..n share a budget A.
- Organ i holds allocation aᵢ and has need dᵢ: the budget that serves its work at the engine's utilisation target ρ.
- Its deficit (local deviation) is

  eᵢ = dᵢ / (ρ aᵢ) − 1    (eᵢ > 0: needs juice; eᵢ < 0: holds surplus)

**The redistribution mediator:**

  daᵢ/dt = κ aᵢ (eᵢ − ē),    ē = Σⱼ aⱼ eⱼ / A

## 3. Properties and proofs

**P1. Conservation.**
- Σᵢ daᵢ/dt = κ (Σᵢ aᵢeᵢ − ē Σᵢ aᵢ) = κ (A ē − ē A) = 0.
- The budget is moved, never created, as in Ch. 29 §8.

**P2. Gradient flow with a Lyapunov function.**
- Substitute eᵢ: aᵢ(eᵢ − ē) = dᵢ/ρ − aᵢ D/(ρA), where D = Σ dᵢ.
- So daᵢ/dt = (κ/ρ)(dᵢ − aᵢ D/A).
- This is the Shahshahani gradient on the simplex Σ aᵢ = A of F(a) = Σᵢ (dᵢ/ρ) ln aᵢ. The Shahshahani metric weights
  by 1/aᵢ, and ∂F/∂aᵢ = dᵢ/(ρ aᵢ), so aᵢ(∂F/∂aᵢ − mean) is exactly the flow above.
- Along the flow dF/dt = Σᵢ (1/aᵢ)(daᵢ/dt)² · (ρ/κ) ≥ 0.
- F is strictly concave, so F is a Lyapunov function and the flow cannot cycle.

**P3. Global exponential convergence.**
- The ODE in P2 is linear: aᵢ(t) = aᵢ* + (aᵢ(0) − aᵢ*) e^(−κDt/(ρA)), with aᵢ* = A dᵢ/D.
- The Jacobian is −(κD/(ρA)) I on the simplex, so every eigenvalue is −κD/(ρA) < 0. This meets Re(λ) ≤ 0 of Ch. 31 §5
  strictly.
- At the equilibrium every organ has the same deficit e* = D/(ρA) − 1. None is starved while another idles.
- `replicator_step` integrates it exactly, in closed form, for any step size.

**P4. Bounds (floors, ceilings, the budget).**
- Allocations are projected onto {loᵢ ≤ aᵢ ≤ hiᵢ, Σ aᵢ ≤ A}.
- The projection is water-filling: organs at a bound keep it, and the rest share the remainder in proportion.
- Budget an organ cannot use (it is at its need or its ceiling) is not spent.

**P5. Reserve and surge.**
- The dual-bath rate channel (the rate tracker) projects the rise in need over one actuation delay:
  R = Σᵢ max(0, ḋᵢ), capped at A/2. R is held back.
- After the flow, R is released continuously to organs whose deficit stays positive, in proportion to their shortfall
  and up to their ceilings.
- This is the controlled release of Ch. 30: continuous state, no switch.

## 4. Evidence
**Mathematics in code.** `tests/test_conveyance.py` (in `verify.py`) checks 20,000 random systems:
- P1 conservation to 1e-9;
- P2, F never decreases;
- P3, the trajectory equals the closed form;
- P4, bounds and budget.

It also runs 2,000 systems over 30 steps and checks the full law never exceeds the budget or breaks a floor. That test
found and fixed one real bug: an organ whose need fell below its device floor was given a ceiling under that floor.

**Simulation.** `hardware/site_exchange.py`: four GPU groups of 16 H100-class GPUs share one site budget (MLPerf gamma).
Held-out seed 929292, 48 scenarios per budget. Results: `results/hardware/SITE_EXCHANGE_HELDOUT_*.json`.

| Site budget (share of TDP) | 70% | 60% | 50% |
|---|---:|---:|---:|
| Site-budget violation minutes, native / independent / **conveyance** | 10.5 / 1.5 / **0** | 45.6 / 10.5 / **0** | 106.1 / 31.3 / **0** |
| Energy (kWh), native / static split / independent / **conveyance** | 142.5 / 117.6 / 104.1 / **103.8** | 139.1 / 107.9 / 103.5 / **102.0** | 127.3 / 97.1 / 101.0 / **96.4** |
| Backlog minutes, static split (the arm that also keeps the budget) / **conveyance** | 32.0 / **1.0** | 89.7 / **8.9** | 187.3 / **72.2** |

**Reading.**
- **Keeping the budget.** Conveyance is the only dynamic arm that never exceeds the site budget.
- **Energy.** It uses the least energy at every budget.
- **Against the only other arm that keeps the budget (static split):** 31-115 fewer backlog minutes.
- **At tight budgets, native and independent sizing show less backlog,** but only by drawing power over the site limit
  for 10-106 minutes, which in a facility trips breakers.
- **When the budget is below total need,** conveyance shares the shortage in proportion to need. That is the unique
  stable point of P3: fair, and not a choice of weights.

## 5. What is not claimed
- This is a simulation on declared device physics.
- The live levers that would carry it are GPU power limits (`nvidia-smi -pl`, DCGM), RAPL package limits, and pod CPU
  limits under a namespace budget. They exist in `omni_controller/muscles.py`, but the exchange between them has not
  run on hardware.
