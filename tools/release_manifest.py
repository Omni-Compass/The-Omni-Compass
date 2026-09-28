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
    "preregistration": ["results/PREREGISTRATION.json", "results/LOCK_AMENDMENTS.json"],
    "license": ["LICENSE", "NOTICE"],
}
LIVE = {
    "set_20": {"run_id": 36366603505, "execution_commit": "18220d4", "repetitions": 10,
               "raw": "results/live/raw/run-36366603505/ (SHA256SUMS_ALL.txt covers every file)"},
    "set_21": {"run_id": 36466558583, "execution_commit": "9e64f7b", "repetitions": 10,
               "raw": "GitHub artifacts, digests in results/live/SET21_ARTIFACTS.json; recomputed by reaggregate run 36485672281"},
}


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
    m = {"release": "Omni-Compass", "written_at_commit": git_head(),
         "written_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "canonical_engine": "symmetric_verified (docs/CANONICAL_ENGINE.md)",
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
