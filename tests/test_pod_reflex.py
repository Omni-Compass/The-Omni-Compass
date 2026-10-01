"""Fast pod reflex on the fake cluster: calm queue -> no read, no write; a queue building up -> the HPA's replica floor
rises to exactly the HPA's own rule (current x busy / target) with busy read from queueing (u = 1 - S/R) and the target
in queue terms (target x request / limit); the queue drained -> the floor is handed back; the kill switch restores the
range and leaves no record."""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Controller, parser, RANGE_ANN
FAKE = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def probe(path, ms):
    with open(path, "w") as f:
        f.write("elapsed_seconds,latency_ms,ok\n")
        for i, v in enumerate(ms):
            f.write(f"{i * 0.5:.1f},{v},1\n")


def main():
    t = Path(tempfile.mkdtemp())
    dep = {"metadata": {"name": "web", "namespace": "default", "annotations": {}},
           "spec": {"replicas": 2, "selector": {"matchLabels": {"run": "web"}},
                    "template": {"spec": {"containers": [{"name": "web", "resources": {"requests": {"cpu": "200m"}, "limits": {"cpu": "500m"}}}]}}}}
    hpa = {"metadata": {"name": "web", "namespace": "default"},
           "spec": {"minReplicas": 1, "maxReplicas": 10, "scaleTargetRef": {"kind": "Deployment", "name": "web"},
                    "metrics": [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 50}}}]},
           "status": {"currentReplicas": 2, "desiredReplicas": 2}}
    st = {"nodes": [], "pods": [], "deployments": [dep], "hpas": [hpa], "configmaps": [], "jobs": []}
    p = t / "state.json"; p.write_text(json.dumps(st)); os.environ["FAKE_KUBE_STATE"] = str(p); os.environ["FAKE_KUBE_LOG"] = str(t / "w.log")
    lat = t / "latency.csv"
    a = parser().parse_args(["--kubectl", FAKE, "--mode", "target", "--interval", "0", "--audit", str(t / "a.jsonl"),
                             "--kill-file", str(t / "kill"), "--latency-file", str(lat), "--slo-ms", "500"])
    c = Controller(a); a.pod_reflex_writes = True   # the writing reflex; by default it gauges only (tested below)
    H = lambda: json.loads(p.read_text())["hpas"][0]
    writes = lambda: (t / "w.log").read_text().splitlines() if (t / "w.log").exists() else []
    probe(lat, [100.0] * 40)                                  # calm: R = S, busy 0
    assert c.pod_reflex() is None and writes() == [], "calm queue must not read or write"
    probe(lat, [40.0] * 40); c.pod_reflex()                    # a pod given more CPU answers in 40 ms, calm
    probe(lat, [100.0] * 40)                                  # back at its own limit, still calm: no queue is read
    assert c.pod_reflex() is None and writes() == [], "a change of the pods' CPU limit is not a queue"
    probe(lat, [100.0] * 5 + [250.0] * 35)                    # S = fastest tenth of this window, 100: R ~ 231, u ~ 0.57
    c.s_floor = 100.0
    out = c.pod_reflex()
    R = (5 * 100 + 35 * 250) / 40; u = 1 - 100 / R; need = int(-(-2 * u / (0.5 * 200 / 500) // 1))
    assert out == {("default", "web"): need} and H()["spec"]["minReplicas"] == need, (out, need, H()["spec"])
    assert H()["metadata"]["annotations"][RANGE_ANN] == "1,10"
    s = json.loads(p.read_text()); s["hpas"][0]["status"] = {"currentReplicas": need, "desiredReplicas": need}; p.write_text(json.dumps(s))
    probe(lat, [100.0] * 40)                                  # queue drained: floor handed back to the operator's 1
    out = c.pod_reflex()
    assert H()["spec"]["minReplicas"] == 1 and c.reflex == {}, H()["spec"]
    (t / "kill").touch(); c.step()
    assert (H()["spec"]["minReplicas"], H()["spec"]["maxReplicas"]) == (1, 10) and RANGE_ANN not in H()["metadata"].get("annotations", {})
    # by default the reflex gauges only: the autoscaler makes and removes pods, I write nothing
    t2 = Path(tempfile.mkdtemp()); p2 = t2 / "state.json"; p2.write_text(json.dumps(st)); os.environ["FAKE_KUBE_STATE"] = str(p2)
    os.environ["FAKE_KUBE_LOG"] = str(t2 / "w.log"); lat2 = t2 / "latency.csv"
    a2 = parser().parse_args(["--kubectl", FAKE, "--mode", "target", "--interval", "0", "--audit", str(t2 / "a.jsonl"),
                              "--kill-file", str(t2 / "kill"), "--latency-file", str(lat2), "--slo-ms", "500"])
    c2 = Controller(a2); probe(lat2, [100.0] * 5 + [250.0] * 35); c2.pod_reflex()
    assert not (t2 / "w.log").exists(), "the gauging reflex must write nothing"
    assert any('"pod_reflex_reading"' in l for l in (t2 / "a.jsonl").read_text().splitlines()), "the reading is recorded"
    print(f"pod reflex: calm 0 writes; queue R {R:.0f} ms vs S 100 ms -> busy {u:.2f} -> floor 2 -> {need} (HPA rule, target 0.5 x 200m/500m);"
          " drained -> handed back to 1; kill restores 1,10")
    print("PASS test_pod_reflex")


if __name__ == "__main__":
    main()
