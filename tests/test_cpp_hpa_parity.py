"""Independent C++ HPA replica law (cpp/src/hpa.cpp) vs the fleet harness HPA (fleet/harness.py) on recorded step streams."""
import csv, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import fleet.sim as FS
from fleet.harness import make_scenario, hpa_step


def main(exe, seeds=(901, 902)):
    rows, expect, first = [], [], {}
    run_id = [None]

    def rec(w, target):
        key = f"{run_id[0]}:{w.name}"
        if key not in first:
            first[key] = w.replicas
        before = w.metric
        hpa_step(w, target)
        rows.append((key, first[key], w.min_rep, w.max_rep, before, target)); expect.append(w.replicas)
    FS.hpa_step = rec
    try:
        for v in ("web", "multi"):
            for s in seeds:
                scn = make_scenario(v, s)
                for arm in ("k8s_hpa70_ca", "k8s_hpa60_ca", "omni_target", "omni_fleet"):
                    run_id[0] = f"{v}-{s}-{arm}"; FS.run(scn, arm)
    finally:
        FS.hpa_step = hpa_step
    tmp = Path(tempfile.mkdtemp())
    with open(tmp / "steps.csv", "w") as f:
        f.write("stream,replicas0,min,max,metric,target\n")
        for k, r0, mn, mx, m, t in rows:
            f.write(f"{k},{r0},{mn},{mx},{float(m)!r},{float(t)!r}\n")
    subprocess.run([exe, str(tmp / "steps.csv"), str(tmp / "out.csv")], check=True, capture_output=True)
    got = [int(r["replicas"]) for r in csv.DictReader(open(tmp / "out.csv"))]
    bad = sum(g != e for g, e in zip(got, expect))
    print(f"C++ HPA vs harness HPA: {len(expect)} steps, {len({r[0] for r in rows})} streams, mismatches = {bad}")
    assert len(got) == len(expect) and bad == 0
    print("PASS test_cpp_hpa_parity")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "cpp" / "build" / "oc_hpa"))
