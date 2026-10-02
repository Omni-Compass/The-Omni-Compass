# Governance

> `SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`. Copyright (c) 2026 The Omni-Compass LLC.

Omni-Compass is owned, maintained and governed by The Omni-Compass LLC. The company decides the roadmap, accepts or
declines contributions (only under `CLA.md`), cuts releases, and holds every right in the software, its mathematics,
its documentation and its marks.

Engineering rules every change follows:
1. The frozen engine (`omnicompass/core.py`, `omnicompass/adapter.py`) and the reference engine are byte-locked; a
   change is a new version with its own proof.
2. Every Python law with a C++ twin changes in the same commit as its twin, and the seal (`results/SEAL.json`) is
   rewritten only after every parity test passes.
3. Every benchmark is preregistered before it runs; its rule decides its label.
4. `python3 verify.py` must end `VERIFICATION: PASS` on every release.
5. The manual (`docs/OMNI_COMPASS_MANUAL.md`) changes in the same commit as the behavior it describes.
