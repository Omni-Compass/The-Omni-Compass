# Security

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright and by patents and patent applications. See [`LICENSE`](LICENSE).

Report suspected vulnerabilities privately to The Omni-Compass LLC rather than in public issues.
The governor issues control actions only through the shield (omnicompass/shield.py, cpp/src/shield.cpp); the
capture script (fleet/capture/kube_capture.sh) is read-only. No component in this repository writes to a live cluster.
