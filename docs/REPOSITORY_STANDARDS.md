# Repository Standards

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

The files the leading repositories carry, the open ones such as Kubernetes and the source-available, commercially licensed ones such as HashiCorp Terraform, Elastic, MongoDB, Redis, CockroachDB and Sentry, and where Omni-Compass carries each. Omni-Compass is published for evaluation and simulation; everything else is licensed (`LICENSE`, `LICENSING_FAQ.md`).

| What a leading repository carries | Omni-Compass |
|---|---|
| License, machine-readable and in full | `LICENSE`, `LICENSES/LicenseRef-OmniCompass-Evaluation-1.0.txt`, SPDX headers, `REUSE.toml` |
| Licensing questions in plain words | `LICENSING_FAQ.md` |
| Notices and third-party components | `NOTICE`, `THIRD_PARTY_NOTICES.md` |
| Disclosures and disclaimers in one place | `DISCLOSURES.md` |
| Patents and trademarks | `PATENTS.md`, `TRADEMARKS.md` |
| Contributor license agreement | `CLA.md` |
| Contributing, code of conduct, governance, ownership | `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, `OWNERS`, `.github/CODEOWNERS` |
| Security policy and contacts | `SECURITY.md`, `SECURITY_CONTACTS` |
| Support | `SUPPORT.md` |
| Changes and roadmap | `CHANGELOG.md`, `ROADMAP.md` |
| Citation and software metadata for archives and crawlers | `CITATION.cff`, `codemeta.json`, `pyproject.toml` (keywords, URLs) |
| Software bill of materials (SPDX and CycloneDX) | `sbom/omni-compass.spdx.json`, `sbom/omni-compass.cdx.json` |
| License scanners (Black Duck, FOSSA, Snyk, ScanCode, REUSE) | `pyproject.toml`, `.fossa.yml`, `.snyk`, `REUSE.toml`, SPDX headers |
| Issue and pull-request templates, including a licensing template | `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md` |
| Dependency updates | `.github/dependabot.yml` |
| Continuous verification | `.github/workflows/verify.yml`, `python3 verify.py` |
| Reproducibility: fingerprinted release, sealed twins, checksummed results | `RELEASE_MANIFEST.json`, `results/SEAL.json`, `SHA256SUMS.txt` in every result folder |
| Rules written before every benchmark run | `docs/GPU_PREREGISTRATION.md`, `docs/REALMS_PREREGISTRATION.md`, `docs/K8S_BOWL_PREREGISTRATION.md` |
| A manual and a printable book | `docs/OMNI_COMPASS_MANUAL.md`, `docs/OMNI_COMPASS_MANUAL.pdf` |
| Every result in one place, with charts | `docs/DOSSIER.md` |
| A one-file archive of the repository | `release/The-Omni-Compass.zip` |

Files present at the commit this page describes; `python3 verify.py` checks the ones the results depend on.
