# XPASS branches, folded in (2026-10-01)

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../../../LICENSE).

Until 2026-10-01 the work was spread over 14 branches. `main` held only an initial commit and an unfilled Azure web-app
template. The full project is now `main`, and the side branches are closed:

- **Eight branches that were only copies of the old `main`** (initial commit and the Azure template, nothing else;
  both commits are now in `main`'s history): `xpass25-chatgpt-aligned-20261001`, `xpass25-hygiene-rebuild`, `xpass25-referee-fix`,
  `xpass25-referee-master`, `xpass25-referee-repair-final-20261001`, `xpass25r-hygiene-fixed`,
  `xpass26-execution-master`, `xpass26-referee-canonical-699`.
- **Three branches that each added one status note**; each note is copied here, unchanged:
  - `xpass25-github-referee-master` → `XPASS25_CURRENT_RELEASE_INDEX.md`;
  - `xpass26-parity-hardened` → `XPASS26_STATUS.json`;
  - `xpass25-referee-repair-20261001` → `XPASS25_R1_INTAKE.md`.
- **`xpass25-referee-repair`** (the full tree, tip `6b72618`; commits `a735907`, `9d81b81`, `6b72618` are the only ones
  not in `main`). It differed from `main` by:
  - fields added to `cpp/include/omnicompass/governor.hpp` that no code used (the matching `governor.cpp` and Python
    changes were never committed);
  - empty GPU tables from runs that never got a machine;
  - the Python 3.12 verify failure, already fixed on `main`.

Nothing of value is only on these branches, so all twelve are to be deleted (an owner deletes them on GitHub:
Code > Branches > the bin icon beside each). Work continues on `main` only.

These notes describe the XPASS packages as their authors wrote them. Where they say "complete source tree", "656" or
"organism", that work lives in the zip packages, not in this repository; `docs/ENGINES.md` says which of their engine
changes are not adopted and why.
