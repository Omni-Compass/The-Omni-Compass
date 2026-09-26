"""Live controller against a fake kubectl (tests/fake_cluster/kubectl): observe writes nothing; target patches HPA
targets within bounds at the correct metric index and records originals; the kill switch restores originals from the
HPA annotation (also after a restart); nodepool respects dry-run, the shield step limit and the scheduling floor."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Controller, parser, ANNOTATION
FAKE = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def cluster(tmp):
    nodes = [{"metadata": {"name": f"n{i}"}, "status": {"allocatable": {"cpu": "32"}, "conditions": [{"type": "Ready", "status": "True"}]}} for i in range(20)]
    pods = [{"status": {"phase": "Running"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "2"}}}]}} for _ in range(10)]
    cpu = lambda v: {"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": v}}}
    mem = {"type": "Resource", "resource": {"name": "memory", "target": {"type": "Utilization", "averageUtilization": 80}}}
    hpas = [{"metadata": {"name": "web", "namespace": "a"}, "spec": {"metrics": [cpu(70)]}, "status": {"currentReplicas": 4}},
            {"metadata": {"name": "api", "namespace": "b"}, "spec": {"metrics": [mem, cpu(60)]}, "status": {"currentReplicas": 3}},
            {"metadata": {"name": "mem-only", "namespace": "c"}, "spec": {"metrics": [mem]}, "status": {"currentReplicas": 2}}]
    st = Path(tmp) / "state.json"; st.write_text(json.dumps({"nodes": nodes, "pods": pods, "hpas": hpas, "used_per_node": "1500m"}))
    os.environ["FAKE_KUBE_STATE"] = str(st); os.environ["FAKE_KUBE_LOG"] = str(Path(tmp) / "writes.log")
    return st


def run(tmp, *args, iterations=3):
    a = parser().parse_args(["--kubectl", FAKE, "--interval", "0", "--audit", str(Path(tmp) / "audit.jsonl"),
                             "--kill-file", str(Path(tmp) / "kill"), *args])
    c = Controller(a)
    for _ in range(iterations):
        c.step()
    return c


def writes(tmp):
    p = Path(tmp) / "writes.log"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def main():
    t = tempfile.mkdtemp(); st = cluster(t)
    run(t, "--mode", "observe"); assert writes(t) == [], "observe wrote"
    print("observe: 0 writes")
    run(t, "--mode", "target")
    S = json.loads(st.read_text()); w = writes(t)
    web = S["hpas"][0]["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"]
    api = S["hpas"][1]["spec"]["metrics"][1]["resource"]["target"]["averageUtilization"]
    assert 50 <= web <= 95 and 50 <= api <= 95 and web != 70
    assert S["hpas"][0]["metadata"]["annotations"][ANNOTATION] == "70" and S["hpas"][1]["metadata"]["annotations"][ANNOTATION] == "60"
    assert S["hpas"][1]["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"] == 80
    assert "annotations" not in S["hpas"][2]["metadata"]
    npatch = sum(1 for x in w if x[0] == "patch")
    print(f"target: HPA targets web 70 -> {web}, api 60 -> {api} (cpu metric at index 1), memory-only HPA untouched, {npatch} patches")
    (Path(t) / "kill").write_text("1")
    run(t, "--mode", "target", iterations=1)
    S = json.loads(st.read_text())
    assert S["hpas"][0]["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"] == 70
    assert S["hpas"][1]["spec"]["metrics"][1]["resource"]["target"]["averageUtilization"] == 60
    assert all(ANNOTATION not in h["metadata"].get("annotations", {}) for h in S["hpas"])
    print("kill switch (new process): originals restored from the HPA annotation, records removed")
    (Path(t) / "kill").unlink()
    marker = Path(t) / "scaled"
    cmd = f"python3 -c \"open('{marker}', 'a').write('{{n}}\\\\n')\""
    run(t, "--mode", "nodepool", "--dry-run", "--node-scale-cmd", cmd, "--max-node-step", "2", iterations=6)
    assert not marker.exists(), "dry-run executed a node command"
    aud = [json.loads(l) for l in (Path(t) / "audit.jsonl").read_text().splitlines()]
    print(f"nodepool dry-run: {sum(1 for r in aud if r.get('why') == 'node pool size')} node commands logged, none executed")
    run(t, "--mode", "nodepool", "--node-scale-cmd", cmd, "--max-node-step", "2", iterations=8)
    ns = [int(x) for x in marker.read_text().split()] if marker.exists() else []
    assert all(18 <= v <= 22 for v in ns), ns
    print(f"nodepool live: {len(ns)} node commands executed, targets {ns} (within the 2-node step of 20, above the request floor)")
    print("PASS test_omni_controller")


if __name__ == "__main__":
    main()
