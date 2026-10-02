# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The release's one identity: RELEASE_MANIFEST.json.

  python3 tools/release_manifest.py           # write the manifest, run verify.py --quick, record its receipt
  python3 tools/release_manifest.py --check   # compare the files with the manifest (verify.py runs this)

The manifest names the commit it was written at and fingerprints (SHA-256) everything that identifies the release: the
canonical engine and the reference engine, the C++ twins (through the seal), the GPU protocol, the live evidence
(execution commit, run id and raw-file digests of sets 20 and 21), the canonical engine declaration, and the receipt
of the verification run made when it was written. One object, so nobody has to reconstruct provenance from history.
"""
from __future__ import annotations

import argparse, datetime, hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "RELEASE_MANIFEST.json"
RECEIPT = ROOT / "results" / "VERIFY_RECEIPT.txt"

GROUPS = {
    "canonical_engine": ["omnicompass/core.py", "cpp/src/core.cpp", "docs/CANONICAL_ENGINE.md"],
    "reference_engine": ["reference/omni_compass_reference_engine.py", "reference/PROVENANCE.json"],
    "cpp_twins_seal": ["results/SEAL.json"],
    "gpu_protocol": ["docs/GPU_PREREGISTRATION.md", "scripts/gpu_paired.sh", "tools/gpu_workload.py", "tools/gpu_reps.py",
                     "omni_controller/gpu_governor.py", "omnicompass/adapter.py", "omni_controller/muscles.py"],
    "live_set_20": ["results/live/LIVE_REPS_20.md", "results/live/raw/run-36366603505/SHA256SUMS_ALL.txt"],
    "live_set_21": ["results/live/LIVE_REPS_21.md", "results/live/SET21_ARTIFACTS.json"],
    "live_set_22": ["results/live/LIVE_REPS_22.md", "results/live/SET22_ARTIFACTS.json",
                    "results/live/reaggregated/LIVE_REPS_36488547793.md"],
    "preregistration": ["results/PREREGISTRATION.json", "results/LOCK_AMENDMENTS.json"],
    "mechanism": ["results/MECHANISM_IDENTITY.json", "tools/mechanism_identity.py", "docs/TRACKING_THEOREM.md",
                  "tools/tracking_bounds.py", "results/TRACKING_BOUNDS.json", "docs/EVIDENCE_LEDGER.md", "RECEIPT.md"],
    "live_set_23": ["results/live/LIVE_REPS_23.md"],
    "live_set_24": ["results/live/LIVE_REPS_24.md"],
    "bowl_law": ["omnicompass/bowl.py", "realms/bowl_arm.py", "omni_controller/gpu_bowl.py", "tools/gpu_wire_check.py",
                 "realms/gpu_card.py", "results/sim/gpu_two_wire/RESULT.json"],
    "gpu_rented_run": ["scripts/gpu_rented_run.sh", "tools/run_hil.py", "tests/fake_gpu/nvidia-smi"],
    "six_organisms": ["tools/run_scale.py", "tools/pool_scale.py", "scripts/scale_ladder.sh", ".github/workflows/six.yml",
                      "results/scale/GRID.md"],
    "license": ["LICENSE", "NOTICE", "DISCLOSURES.md"],
    "realms": ["realms/catalog.csv", "realms/plants.py", "realms/presets.py", "realms/harness.py",
               "tools/realms_catalog.py", "tools/run_realms.py", "docs/REALMS_PREREGISTRATION.md"],
}
# engine components checked identical to this release's at each execution commit (tools/mechanism_identity.py
# components F, C, h, G, dt, recomputed from the source at that commit); the Kubernetes actuator map and shield are as
# at the execution commit
SAME = ["F", "C", "h", "G", "dt"]
LIVE = {
    "set_20": {"run_id": 36366603505, "execution_commit": "18220d4", "repetitions": 10, "plant": "kind (GitHub Actions)",
               "engine_components_identical_to_release": SAME,
               "raw": "results/live/raw/run-36366603505/ (SHA256SUMS_ALL.txt covers every file)"},
    "set_21": {"run_id": 36466558583, "execution_commit": "9e64f7b", "repetitions": 10, "plant": "kind (GitHub Actions)",
               "engine_components_identical_to_release": SAME,
               "raw": "GitHub artifacts, digests in results/live/SET21_ARTIFACTS.json; recomputed by reaggregate run 36485672281"},
    "set_22": {"run_id": 36488547793, "execution_commit": "cfdc17c", "repetitions": 10, "plant": "kind (GitHub Actions)",
               "load": "open-loop, fixed rate (equal work)", "engine_components_identical_to_release": SAME,
               "raw": "GitHub artifacts, digests in results/live/SET22_ARTIFACTS.json; recomputed by the reaggregate workflow"},
}


def sha_files(paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(p.encode() + b"\0" + (ROOT / p).read_bytes())
    return h.hexdigest()


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def git_head():
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def check():
    """Returns a list of mismatches (empty when every fingerprinted file matches)."""
    if not MANIFEST.exists():
        return ["no RELEASE_MANIFEST.json: run python3 tools/release_manifest.py"]
    m = json.loads(MANIFEST.read_text()); bad = []
    for group, files in m["files"].items():
        for p, h in files.items():
            if not (ROOT / p).exists():
                bad.append(f"{group}: {p} is missing")
            elif sha(p) != h:
                bad.append(f"{group}: {p} changed since the manifest (python3 tools/release_manifest.py)")
    r = m.get("verification_receipt")
    if r and (not RECEIPT.exists() or sha(RECEIPT.relative_to(ROOT)) != r["sha256"]):
        bad.append("verification receipt: results/VERIFY_RECEIPT.txt differs from the manifest")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        bad = check()
        print("\n".join(bad) if bad else "release manifest matches the files")
        return 1 if bad else 0
    mi = json.loads((ROOT / "results" / "MECHANISM_IDENTITY.json").read_text())
    canon = mi["configurations"][mi["canonical"]]
    tests = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_*.py")) + ["verify.py"]
    head = git_head()
    m = {"release": "Omni-Compass", "release_id": f"omni-compass-{head[:12]}", "written_at_commit": head,
         "written_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "canonical_engine": "symmetric_verified (docs/CANONICAL_ENGINE.md)",
         "mechanism_id": canon["mechanism_id"], "mechanism_configuration": mi["canonical"],
         "mechanism_components": canon["components"],
         "alternative_embodiments": {n: c["mechanism_id"] for n, c in mi["configurations"].items() if not c["canonical"]},
         "fingerprints": {"engine_sha256": sha("omnicompass/core.py"), "cpp_sha256": sha("cpp/src/core.cpp"),
                          "controller_sha256": sha("omni_controller/controller.py"),
                          "observation_map_sha256": canon["components"]["h"], "authority_map_sha256": canon["components"]["G"],
                          "actuator_map_sha256": canon["components"]["M_act"], "shield_sha256": sha("omnicompass/shield.py"),
                          "gpu_protocol_sha256": sha_files(GROUPS["gpu_protocol"]),
                          "preregistration_sha256": sha_files(GROUPS["preregistration"] + ["docs/GPU_PREREGISTRATION.md"]),
                          "test_suite_sha256": sha_files(tests)},
         "files": {g: {p: sha(p) for p in fs} for g, fs in GROUPS.items()},
         "live_evidence": LIVE,
         "physical_meter_results": "none yet: the GPU bench (scripts/gpu_paired.sh) has not been run on a card"}
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n")
    r = subprocess.run([sys.executable, str(ROOT / "verify.py"), "--quick"], capture_output=True, text=True, cwd=ROOT)
    RECEIPT.write_text(f"verify.py --quick at commit {m['written_at_commit']}, {m['written_at']}\n\n" + r.stdout)
    ok = r.returncode == 0 and "VERIFICATION: PASS" in r.stdout
    m["verification_receipt"] = {"file": "results/VERIFY_RECEIPT.txt", "sha256": sha("results/VERIFY_RECEIPT.txt"), "passed": ok}
    MANIFEST.write_text(json.dumps(m, indent=1) + "\n")
    print(f"RELEASE_MANIFEST.json written at {m['written_at_commit'][:12]}; verification {'PASS' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
