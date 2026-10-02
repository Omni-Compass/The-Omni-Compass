# XPASS25 R1 referee repair

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../../../LICENSE).

This branch is an intake marker for the repaired XPASS25 source package. It is deliberately **not** labeled runnable until the complete source tree is committed.

Repairs completed locally on 2026-10-01:
- C++ governor now mirrors Python disruption-budget / optional empty-only node-down policy.
- C++ fleet wrapper corrected from down_dwell=1 to Python FLEET_MODE down_dwell=8.
- C++/Python governor parity: five modes, 4,320 directives per mode, 0 discrete mismatches, worst numeric difference 4.441e-16.
- Twins parity test corrected to use strict 1e-12 floating tolerance instead of bit-for-bit equality for derived statistics; 500-case quick set passed.
- XPASS25 canonical/referee targeted pytest: 3 passed.
- Historical core/adapter hash lineage recorded explicitly; canonical six-state/eight-line engine was not edited in this repair.

Evidence posture:
- 699 candidate audit rows.
- 656 current canonical benchmark target inventory.
- 656 is not a claim of 656 E3/E4-proven actuators.
- Complete-organism N remains OPEN_DISCOVERY under the admission gate.
- E3 Kind and E4 NVIDIA remain READY_TO_RUN_NOT_CLAIMED.
- GitHub Actions quota exhaustion is confirmed from the supplied billing notice, but it does not by itself establish the root cause of individual 30–45 second verify failures.
