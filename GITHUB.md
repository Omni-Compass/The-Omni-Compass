# Publish this tree

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
