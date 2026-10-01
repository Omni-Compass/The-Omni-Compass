# Which engine is which

There is **one** engine. Every other engine-looking file in this repository is either its required C++ twin or a frozen
copy of where it came from. Nothing else runs.

| File | Role | Runs? |
|---|---|---|
| `omnicompass/core.py` | **The engine** (`symmetric_verified`): six states, eight lines, RK4 with microsteps. Everything Omni does goes through it. | yes |
| `cpp/src/core.cpp`, `cpp/include/omnicompass/core.hpp` | The same engine in C++. Required: `verify.py` checks it against the Python on every fixture. | yes (twin) |
| `docs/handoff/mathematics/omni_compass_engine_source_c527df2d.py` | The original source as handed over (sha256 `c527df2d…`). Kept unchanged as proof of origin and as the parameter authority. | no (frozen) |
| `reference/omni_compass_reference_engine.py` | The same original with comments stripped (`tools/strip_reference.py`); same program fingerprint (`reference/PROVENANCE.json`). | no (frozen) |

Fingerprints of the running engine, its parts and its twin: `results/MECHANISM_IDENTITY.json` and `RELEASE_MANIFEST.json`.
`verify.py` fails if any of them changes without a new seal.

## Engines from outside packages, not adopted

Copies of this repository passed around as zips (the XPASS packages) carry changes that are **not** in the engine here:

- `omnicompass/batch_claim1.py`: a vectorised variant that applies u during the RK4 step (CLAIM1). No C++ twin; not
  verified against the 500 fixtures.
- an adapter that defaults to CLAIM1, takes the target sign from the starting state and adds a disruption budget. Its
  C++ governor was only partly ported, which is where the reported Python/C++ mismatches came from.

None of these enter before the GPU confirmation run (the engine is frozen for it, `docs/GPU_PREREGISTRATION.md`). Any of
them can be adopted afterwards only as a full change: Python and C++ together, the parity tests and `verify.py` green,
and a new mechanism id.

## The rule from here

One engine, one twin, two frozen originals. A new version **replaces** the old one in place, with a new seal; it is never
added beside it. Older states are in git history and `docs/HISTORY.md`, not in extra files.
