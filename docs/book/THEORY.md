# The Unified Circle Principle

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../../LICENSE).

![Plate 1. The Unified Circle Principle](plates/unified_circle_principle.jpg)


Omni-Compass begins with one idea: a system that is closed, bounded and pulled toward a center cannot run away, and
everything it does is a return. I call this the closed circle. This chapter states the principle as I hold it, in its
mathematical form, and then says plainly which parts of it the software uses and which parts belong to the wider theory
the software grew out of.

## The statement

    dX/dt = G(X),        X(0) in Omega, a subset of R^n
    G(X) . n(X) <= 0     on the boundary of Omega
    grad L(X) . G(X) <= 0
    =>  lim (t -> infinity) X(t) in M*, a subset of F

Read line by line:

1. **dX/dt = G(X).** The state X moves according to one law G. There is no outside hand: every change comes from the
   law and the state it is in.
2. **X(0) in Omega.** The state starts inside the admissible region Omega: the set of states that are physically and
   operationally allowed.
3. **G(X) . n(X) <= 0 on the boundary.** At the wall of Omega, the flow never points outward (n is the outward normal).
   Nothing that starts inside can cross out. In control theory this is the Nagumo condition: Omega is forward
   invariant.
4. **grad L(X) . G(X) <= 0.** There is a function L, the energy of the bowl, that never increases along the motion.
   This is a Lyapunov condition.
5. **=> X(t) settles in M*.** Together, an invariant container and a non-increasing energy force every path into the
   set M* where the energy stops falling: the bottom of the bowl.

The power of the statement is that it does not depend on the particular disturbance. Every input up to the size the
container is built for has the same answer before it is asked: the state stays inside and returns. That is what I mean
when I say that a closed circle holds the answer to every question that can be put to it.

## Closure, admissibility, boundedness

![Plate 2. Closed-circle structural architecture of the unified law](plates/closed_circle_architecture.jpg)


The theory sets five requirements on any law that claims to close the circle:

| Requirement | Meaning | In the engine |
|---|---|---|
| Finite deviation | the distance from the admissible state has a ceiling, abs(E) <= E_max | the deviation state E drains faster than it can fill |
| Finite curvature | the landscape the state moves on has no infinite slopes or pits | the drive is bounded by tanh; the authority is clipped |
| Global conservation | what flows in is matched by what flows out | the drain and the bath's friction match the drive |
| Recurrence | a disturbed state returns arbitrarily close to where it was | convergence to the target pole at rate K_P |
| One law | every subsystem obeys the same law, no special cases | one engine, one bowl, every muscle |

## The closed circle tested

![Plate 3. The closed circle tested](plates/closed_circle_tested.jpg)


The canonical evolution law has four parts: deviation is damped nonlinearly and coupled to alignment and to the basin;
alignment relaxes toward unity and responds to deviation; the basin's curvature evolves with internal structure; damping
absorbs excess growth and redistributes energy. Bounded random noise is permitted; divergence is not. A cycle is
identified when the system returns arbitrarily close to a prior state within a bounded tolerance under noise. The state
advances stepwise under a stable numerical integrator with boundedness checks. Under parameter sweeps the test is
always the same three checks: no divergence, bounded, recurring.

## Symmetry and conservation in the closed circle

![Plate 4. Symmetry principles and conservation laws in the closed circle](plates/symmetry_conservation.jpg)


Every conservation law is the shadow of a symmetry (Noether). The closed circle carries four:

| Symmetry | Conserved | In Omni-Compass |
|---|---|---|
| Temporal (the law does not change with time) | energy | the same law governs every decision; the receipt compares like with like |
| Spatial (the law does not depend on where) | momentum | the same law governs every muscle in every realm |
| Rotational | angular momentum | the bowl is symmetric about its center; the engine is symmetric between its poles |
| Internal alignment | alignment invariance | the alignment state is pulled to its pole whichever pole it is |

Around them sit the boundary conditions of the circle: maximum deviation (the boundary limit), topological closure
(bounded wholeness), nonlinear dynamics (complex interactions), resonant reversal (feedback return), energy-momentum
conservation, and cross-scale invariance (scale-independent patterns).

## Scale invariance

![Plate 5. Scale invariance and structural universality](plates/scale_invariance.jpg)


The theory claims that one bounded nonlinear action has the same form at every scale: cosmological (curvature
geometry, compression and expansion, thermodynamic cycling), galactic (rotation curves, mass-energy distribution),
stellar (gravitational compression, fusion equilibrium, radiative transport), atomic (electron displacement, orbital
coherence, radiative damping) and quantum (localized deviation wells, bounded oscillation, finite amplitude). The
universal criteria for such a law are that it operates at every scale and preserves bounded deviation, finite curvature
and recurrence. The state vector carries the same meaning at every scale: E the deviation magnitude, U the coherence or
flow alignment, S the structural curvature or basin geometry, B the redistribution or damping.

## The lineage of unification

![Plate 6. The lineage of unification](plates/lineage_of_unification.jpg)


Each step in the history of physics unified two things that had been separate: geometry formalized structure; motion
was unified across earth and sky; astronomy revealed recurrence; fields replaced action at a distance; curvature unified
gravity, though singularities remained; symmetry came to govern the quantum realm. The closed circle is offered as the
next step: unity without divergence, a single bounded law with no singularity and no runaway.

## What is tested and what is theory

![Plate 7. A candidate for a closed, unified law](plates/candidate_closed_law.jpg)


The software uses the engineering core of this principle, and every part of that core is checked:

- The six-state engine, its bounded control command held through the integration step, and the convergence of its
  alignment state to its pole are proved (`docs/TRACKING_THEOREM.md`) and tested against a C++ twin.
- The invariance and boundedness of each engine state were checked state by state (Chapter "Closing the Circle").
- The bowl law pulls every muscle's service reading to the middle of its band under a bounded, smooth force, and its
  behavior is measured in simulation and on real software.

The wider claims - one law across every physical scale, the cosmological and quantum readings, the candidate unified
action - are the theory from which Omni-Compass was built. They are stated here so that the engineer understands where
the design comes from. They are not claims that the software has measured, and no result in this book depends on them.

# The Four-Piece Engine

![Plate 8. The Omni-Compass Grand Theory: the four pieces](plates/grand_theory.jpg)


The engine is built in four pieces, stacked like the stages of a press, each feeding the next:

| Piece | Name | What it establishes |
|---|---|---|
| 1 | Foundational Engine | the base laws, the states and the boundaries: a closed, bounded, nonlinear adaptive engine with a four-state dynamical structure (misalignment, alignment recovery, coherence potential, path interaction), bounded convergence and persistence with decay, intrinsic feedback and stabilization, and an empirical validation framework for recovery |
| 2 | Geometric Response | geometric alignment and response dynamics: a geometric coherence field, a unified potential governing geometric deformation, and the propagation mechanism of that response |
| 3 | Coherence Evolution | coherence through response and adaptation: the coherence-response envelope, the system response field, and the coupling of coherence state with response propagation |
| 4 | Unified Master Field Law | one coherent field structure: it integrates pieces 1-3 into one closed dynamical structure with a unified potential governing all subsystems, bidirectional propagation between engine state, geometry and response, bounded convergence across the whole system, and no external authority: all evolution emerges from internal coupling |

The four pieces compress every domain through one center core. The compression process has four stages: the domains
unordered; compression in progress; coherence achieved; return to equilibrium. The result has four properties:
coherent, bounded, admissible, stable - one law, one return, one cycle.

**The 24 domains.** The theory gathers 24 domains into four quadrants around that core:

| Quadrant | Domains |
|---|---|
| 1. Foundational structures | Newtonian gravity; Maxwell electromagnetism; Einstein relativity; Schrodinger quantum mechanics; Shannon information theory; Dirac quantum field theory |
| 2. Dynamics and symmetries | Noether symmetry laws; Hamiltonian dynamics; Lagrangian mechanics; thermodynamics; topology; differential geometry |
| 3. Coherence evolution | gauge field theory; fluid dynamics; field theory; discrete mathematics; solid-state physics; plasma physics |
| 4. Complex systems and integration | astrophysics; consciousness and information integration; biological systems and self-organization; universal mathematical structure; systems theory and complex adaptive systems; the unified Omni-Compass domain (the unified admissible state) |

![Plate 9. The unified container of all reality: 24 domains, four-piece engine, one closure law](plates/four_piece_engine.jpg)

![Plate 10. The four quadrants and the compression process](plates/unified_container.jpg)

![Plate 11. The closure law and the closed-circle engine](plates/closure_law.jpg)

**In the software,** the four pieces appear as the engine's state equations (piece 1: deviation, alignment, memory and
basin), the basin potential and its flow (piece 2), the bath that absorbs and redistributes (piece 3), and the one
governor that couples every muscle to one law with no outside authority (piece 4).

# The Compass

![Plate 12. The Omni-Compass rose](plates/compass_rose.jpg)

![Plate 13. The Omni-Compass Principle](plates/omni_compass_principle.jpg)


The Omni-Compass rose is the whole mechanism drawn as one picture.

**The ring.** Twenty-four letters, the complete Greek alphabet from Alpha to Omega: the complete set, nothing missing,
one letter for each domain. On a ring the end runs back into the beginning: after the last letter the ring returns to
Alpha. That is the closed circle: identity, return, cycle.

**The four points.** Four letters are lifted out of alphabetical order and set on the four points of the rose:

| Point | Letter | Mark | Meaning in the engine |
|---|---|---|---|
| North | Alpha, the first | + | the positive pole of the alignment's double well, U = +1 |
| South | Omega, the last | - | the negative pole, U = -1 |
| East | Beta | > | the drive coming in (the beta terms that fill the deviation) |
| West | Gamma | < | the coupling that carries energy out to the bath, where friction absorbs it |

The north-south line is polarity; the east-west line is flow in against flow out. A system stays inside its circle
exactly when what flows out can always match what flows in.

**The inner marks.**

| Mark | Meaning | In the mechanism |
|---|---|---|
| + and - | the two polarities | the two poles of the double well |
| > and < | push out, pull in | the antagonist pair: the up force and the down force |
| the double arrow | exchange both ways | the two-way wire: read in, write out |
| the up-tack | the ceiling | the cover: nothing goes past the top |
| approximately-equal | the wave, the tolerance | the band and its cushion: hold near the center |
| the star | the guiding star | the target the needle points to |

**The center.** The spiral at the middle is the attractor: every path winds inward to one point.

**Opposite letters.** Across the center, zeta faces xi: both are the engineer's symbol for the damping ratio, and a
damping ratio of one is the critical glide to the center with no overshoot. Lambda faces psi: the eigenvalue and the
wave function of the eigenvalue equation.

# Basins, Polarity and the Dual-Basin Engine

## Geometric funneling and basin formation

![Plate 14. Geometric funneling and basin formation](plates/geometric_funneling.jpg)


A basin forms in three stages. While the driving tension T is low, curvature is weak and there is no dominant basin:
flows spread outward. As T increases, curvature concentrates and a positive feedback loop begins. Then a stable
geometric funnel forms: self-reinforcing curvature, finite depth, bounded deviation, with the boundary abs(E) <= E_max
respected. Structure emerges from fluctuation through curvature concentration and feedback.

In the engine, the basin state S rolls down its potential Phi(S) to a stable bottom; in the bowl, every muscle's service
reading is pulled into the bottom of its own funnel.

## Polarity

Two like charges repel without anyone pushing them: the force comes from the shape of the field. A wall built of like
polarity at the edge of a band pushes the state back harder the closer it comes (as one over the distance squared),
and two such walls cancel at the center, where the state comes to rest. This is the boundary condition of the closed
circle written as a force: the field itself points inward at the wall.

The repulsion does not create energy: the field stores what it took to bring the charges together. What is gained in
the computer is that the force is computed rather than spent: the brain computes it at no physical cost, and the
machine's energy is saved because its knob no longer fights itself.

A symmetric pair of repelling walls was tested on the modelled GPU card. It raised work per energy but also raised the
time spent past the service line, because the lower wall pushed capacity away when the card was calm. It was removed.
The upper wall alone remains a candidate.

## The dual-basin engine

![Plate 15. The Omni-Compass dual-basin engine](plates/black_hole_engine.jpg)


The dual-basin engine is a recursive transform with five stages:

1. **Compression.** Two outer basins of positive polarity draw matter and energy inward in a spiral; rotation organizes
   the flow; compression increases toward the center.
2. **Saturation.** At the center, two cores of negative polarity meet back to back; the basin structure S reaches its
   critical value and the curvature reaches its maximum.
3. **Transition (ignition).** Where the cores touch, the transition operator T(X) = sigma(S - S_c) T(X) activates:
   compression halts and redistribution begins.
4. **Redistribution.** Two axial jets carry the excess out along the axis, with opposite helicity to the inflow.
5. **Reset and recurrence.** The domain relaxes and the cycle repeats.

The core mathematics is a bounded flow: dX/dt = G(X, t) with abs(G(X)) <= C_G, a curvature envelope K(X) <= K_max, and
a redistribution term that activates only at saturation. The state X = (E, U, S, B) stays in its admissible domain,
whose horizon boundary is forward invariant (the Nagumo condition again).

**For an engineer,** the transform reads: pull toward the center (compression); a wall where the muscle saturates;
and, when one muscle saturates, move the excess to its siblings rather than hammering it (redistribution). The first two
are built into the bowl. Redistribution across muscles is designed and not yet built; it is on the roadmap.

# Closing the Circle in the Engine

![Plate 16. Mathematical integration](plates/mathematical_integration.jpg)

![Plate 17. The engine core: the governing law in motion](plates/engine_core.jpg)


Each state of the engine was checked against the closed-circle conditions:

| State | Closed? | Why |
|---|---|---|
| E, deviation | closed | it drains at rate alpha_E while its inputs are bounded (the drive is capped by tanh) |
| U, alignment | closed | the cubic term mu U (1 - U^2) pushes back hard from far out |
| I_U, memory | closed | it forgets at rate lambda_I |
| B, the bath | closed | the friction omega_B / Q_B settles it |
| S, the basin | closed on the positive side; open on the negative side below an unstable ridge | Phi(S) carries a cubic term, so the landscape falls away below the ridge (at S = -3.5 with the default parameters) |

Three openings were found and each has its closure:

1. **The basin's negative side.** A quartic term in Phi(S) would give the bowl a wall on both sides. This changes the
   frozen engine and is a new version with its own proof.
2. **The outer loop.** The frozen live governor computes the push and pull u and uses it as a convergence signal; it
   does not send u to a lever. The bowl closes this loop: reading, force, plug, lever, read-back. On the modelled card
   this is the difference between +0.1% and several percent of work per energy (the one-wire governor against the
   corrected two-wire bowl, `results/sim/gpu_two_wire/`).
3. **The corner.** clip() is a hard stop; tanh is its smooth form. The bowl uses tanh.

# The Physics of a Processor

A GPU's firmware raises its clock one step at a time whenever there is work and room; each higher clock needs a higher
voltage, and dynamic power rises with the clock times the square of the voltage, so the top of the clock range is where
each extra step of speed costs the most watts. When the draw crosses the power limit, the firmware knocks the clock down
several steps; with room again, it climbs again. On a busy card this repeats many times a second. The clock saws against
the limit, the overshoots burn watts before the limiter catches them, and the card spends its time at the steepest part
of its power curve. The power is the burner; the cooling removes the heat at its own pace; the limiter turns the burner
down so the cooling can catch up, and the boost turns it back up.

The firmware does not aim at a balance point because it cannot see the job: it does not know whether the work is a
response due in milliseconds or a batch due overnight, the right point moves with the workload, the room and the chip,
and a limiter is simple to prove safe. The vendor default is set for maximum performance, and the electricity bill is the
customer's.

Omni-Compass sits on the customer's side, where the job's service line is known. It holds two wires: the clock ceiling
sets how high the boost may climb, and the power limit becomes a lid set just above what that ceiling draws. The boost
stops at the bottom of the bowl instead of slamming into the wall; the limiter rarely needs to act. Every watt kept off
the chip is saved twice in a data center: once at the chip and again at the chillers that would have carried its heat.

# The Six Organisms and the Benchmark Grid

Omni-Compass is benchmarked on six organisms, each run native and with Omni-Compass on top on the same seed, the same
load and the same clock: Compute / AI / Cloud (345 muscles), Physics / Robotics / Autonomous (262), Energy / Facility /
Industrial (282), Distribution / Specialized (337), the four stacked with every duplicate kept (1,226), and the whole
tower with every muscle once (656).

Each organism is run at 1, 10, 100 and 1,000 paired runs and at 1, 10, 100 and 1,000 copies of the organism on one
clock. Every receipt shows work per energy, work, energy, the time spent outside the service line, and whether every
knob was handed back.

On a GPU machine the real card is wired into each organism as one more muscle of its NVIDIA GPU family; its own power
meter and its requests are counted in the organism's receipt, kept apart from the modelled plants and also added to
them. Real Kubernetes is benchmarked separately on real clusters.

The six organisms are models (evidence class S). They show how the law behaves across hundreds of kinds of machine at
once and whether its effect is stable as the count and the size grow. Real Kubernetes and the real card are the anchors
measured on real software and a real meter.

# The Economics of a Receipt

Run the stack native and print the receipt. Run the same stack with Omni-Compass and print the receipt. The difference
is the gain, read from either side: more work for the same energy, or the same work for less energy and fewer machines.

The license fee is set against the measured gain on the customer's own receipt. On a stack that costs one hundred, a
measured gain of ten is worth ten; the fee is a share of that ten, and the customer keeps the rest. Percentages from
different parts of a stack are not added into one bill: the invoice is one gain, measured once.

The value a customer sees comes in three forms, each on its own line of the receipt:

1. **Work per energy** - more finished work per kilowatt-hour.
2. **Capacity** - the same work on fewer machines in service; it becomes a cost reduction when the released machines are
   returned to the cloud or switched off by the platform around Omni-Compass.
3. **Service** - faster responses and fewer breaches at the same load.

The babysitting tax - the people and tools kept on the clock to set caps, answer pages and turn knobs back after a run
or a crash - is the cost Omni-Compass removes by holding the knobs and returning them itself.
