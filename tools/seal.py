"""The seal: every law that exists in Python and in C++, locked together.

  python3 tools/seal.py            # build the C++, run every twin's parity test, and only if all pass write SEAL.json
  python3 tools/seal.py --check    # compare the files with SEAL.json (verify.py runs this)

SEAL.json (results/SEAL.json) records, for each twin, the SHA-256 of its Python file and of its C++ files, the parity
test that proved them equal, and when. A change to either side of a twin breaks the seal until its parity test passes
again and the seal is rewritten, so the Python and the C++ can never drift apart unnoticed. Mechanisms that exist in
Python only are listed too, so nobody takes them for twinned.
"""
from __future__ import annotations

import argparse, datetime, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
SEAL = ROOT / "results" / "SEAL.json"

TWINS = {
    "core engine (six-state equations)": {"python": ["omnicompass/core.py"],
        "cpp": ["cpp/src/core.cpp", "cpp/include/omnicompass/core.hpp"], "proof": "cpp/scripts/compare_results.py on fixtures/current_500_*.csv"},
    "governor (allocation laws)": {"python": ["omnicompass/adapter.py"],
        "cpp": ["cpp/src/governor.cpp", "cpp/include/omnicompass/governor.hpp"], "proof": "tests/test_cpp_governor_parity.py"},
    "safety shield": {"python": ["omnicompass/shield.py"],
        "cpp": ["cpp/src/shield.cpp", "cpp/include/omnicompass/shield.hpp"], "proof": "tests/test_cpp_shield_parity.py"},
    "HPA replica law": {"python": ["fleet/harness.py"],
        "cpp": ["cpp/src/hpa.cpp", "cpp/include/omnicompass/hpa.hpp"], "proof": "tests/test_cpp_hpa_parity.py"},
    "closure law (machines)": {"python": ["omnicompass/closure.py"],
        "cpp": ["cpp/src/closure.cpp", "cpp/include/omnicompass/closure.hpp"], "proof": "tests/test_cpp_closure_parity.py"},
    "conveyance law (the conserved budget)": {"python": ["omnicompass/conveyance.py"],
        "cpp": ["cpp/src/conveyance.cpp", "cpp/include/omnicompass/conveyance.hpp"], "proof": "tests/test_cpp_conveyance_parity.py"},
}
PYTHON_ONLY = {
    "omni_controller/gpu_governor.py": "GPU governor (share floor, busy gate, speed lock)",
    "omni_controller/muscles.py": "Kubernetes and hardware muscles (convey, rightsize, coldstart, batch, contain, cooling, CPU/GPU connectors)",
    "omni_controller/controller.py": "Kubernetes controller (HPA target, pod reflex, machines, strict replicas)",
    "omnicompass/nervous_system.py": "nervous system (authority per organ, living band)",
    "omnicompass/compass.py": "compass readings",
    "hardware/node_exchange.py": "CPU + GPU on one power budget (simulation harness; the law itself is twinned above)",
}


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def prove():
    """Build the C++ and run every twin's parity test; raises on any failure."""
    import verify
    tmp = Path(tempfile.mkdtemp()); b = verify.build_cpp(tmp)
    subprocess.run([str(b / "oc_run_fixture"), str(ROOT / "fixtures/current_500_inputs.csv"), str(tmp / "cpp.csv")], check=True)
    subprocess.run([sys.executable, str(ROOT / "cpp/scripts/compare_results.py"), str(ROOT / "fixtures/current_500_expected.csv"),
                    str(tmp / "cpp.csv"), str(tmp / "cpp.json")], check=True, capture_output=True)
    assert json.loads((tmp / "cpp.json").read_text())["pass"], "core engine: C++ differs from the 500 fixtures"
    from tests import (test_cpp_governor_parity, test_cpp_shield_parity, test_cpp_hpa_parity, test_cpp_closure_parity,
                       test_cpp_conveyance_parity)
    for m in ("power_protect", "throughput", "fleet", "fleet_balanced", "fleet_wear"):
        test_cpp_governor_parity.main(str(b / "oc_governor"), 20, m)
    test_cpp_shield_parity.main(str(b / "oc_shield"), 8)
    test_cpp_hpa_parity.main(str(b / "oc_hpa"), (901,))
    test_cpp_closure_parity.main(str(b / "oc_closure"), 1)
    assert test_cpp_conveyance_parity.main(str(b / "oc_conveyance"), 200) < 1e-9


def check():
    """Returns a list of broken twins (empty when every sealed file is unchanged)."""
    if not SEAL.exists():
        return ["no seal: run python3 tools/seal.py"]
    seal = json.loads(SEAL.read_text()); broken = []
    for name, t in TWINS.items():
        rec = seal["twins"].get(name)
        if rec is None:
            broken.append(f"{name}: not in the seal"); continue
        for p in t["python"] + t["cpp"]:
            if rec["sha256"].get(p) != sha(p):
                broken.append(f"{name}: {p} changed since the seal ({t['proof']} must pass, then python3 tools/seal.py)")
    return broken


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        broken = check()
        print("\n".join(broken) if broken else f"seal intact: {len(TWINS)} Python/C++ twins")
        return 1 if broken else 0
    prove()
    out = {"sealed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "rule": "each twin's Python and C++ files were proven equal by its parity test before these hashes were written",
           "twins": {name: {"proof": t["proof"], "sha256": {p: sha(p) for p in t["python"] + t["cpp"]}} for name, t in TWINS.items()},
           "python_only": PYTHON_ONLY}
    SEAL.write_text(json.dumps(out, indent=1) + "\n")
    print(f"sealed {len(TWINS)} Python/C++ twins after every parity test passed; {len(PYTHON_ONLY)} mechanisms Python only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
