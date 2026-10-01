# Formal status

Not a global-stability proof of the forced six-state system. Proofs and their evidence classes:
`docs/TRACKING_THEOREM.md`; every statement's class: `docs/EVIDENCE_LEDGER.md`.

Held:

- Isolated S-flow is the gradient of Phi (same formula in both cores).
- (T) Unsaturated: dU/dt = KP (sigma − U); V = e²/2 has dV/dt = −KP e² on that channel (Theorem 1).
- (T) Saturated, with the U drift bounded by F_bar < U_AUTHORITY: V decreases wherever e ≠ 0; over the declared
  parameter box F_bar = 16.86 < 25, so this holds over the box in continuous time (Theorem 2).
- (T, constant computed) Sampled-data RK4 controller: e_(k+1) = 0.88 e_k + d_k; with epsilon_h computed over the
  frozen fixtures (V), the ultimate bound 0.0315 lies inside the 0.10 basin (Theorem 3).
- (T continuous, V discrete) Admissible box forward invariant (Theorem 4).

Open:

- epsilon_h and discrete invariance proved over the whole box (interval arithmetic).
- Inheritance embedding / intertwining residual against a real plant (Closed Structure Def. 11.1): instrumented in
  the GPU bench (`tools/gpu_reps.py`, representation fidelity), not yet measured on a card.
- Mapping of monograph Theorem 5.6 onto (E,U,I_U,S,B).
- A tracking bound for printed_eight_line (logistic U drift).

Default core remains symmetric_verified (mechanism id in `results/MECHANISM_IDENTITY.json`).
