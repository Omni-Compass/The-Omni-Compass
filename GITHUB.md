# Publish this tree

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](LICENSE).

This directory is the GitHub root.

```bash
cd OmniCompass_repo
git init
git add .
git commit -m "Omni-Compass mechanism, harnesses, and verifier"
```

Replace `NOTICE` contact before the first public push. Confirm patent counsel
has signed off on disclosure. Choose whether `LICENSE` stays source-available
or is swapped for the company’s executed form.

CI: `.github/workflows/verify.yml` runs `python verify.py --quick`.
Full reproduction: `python verify.py` (15–30 minutes).

Do not put customer telemetry in this repo.
