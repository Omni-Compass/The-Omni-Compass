"""Energy to where the work is, against the fake kubectl: each machine's idle CPU (inside the living band, less the
requests of every other pod on it) is conveyed to the serving pods on it as their CPU limit, resized in place with no
restart and never below the operator's limit; requests are untouched; a security hold blocks expansion; a machine
crowded with other work leaves the operator's limit as it is; the kill switch returns every pod to the operator's
limit. A machine closed to new work that still carries work keeps counting in service, and my machine orders are
judged by the machines open to work."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Controller, Kube, parser, snapshot
from omni_controller.muscles import CPU_ANN
FAKE = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def pod(name, node, app, req="200m", lim="500m", phase="Running"):
    return {"metadata": {"name": name, "namespace": "default", "labels": {"app": app}}, "status": {"phase": phase},
            "spec": {"nodeName": node, "containers": [{"resources": {"limits": {"cpu": lim}, "requests": {"cpu": req}}}]}}


def state(tmp, hold="false"):
    ready = [{"type": "Ready", "status": "True"}]
    nodes = [{"metadata": {"name": f"w{i}"}, "spec": {}, "status": {"allocatable": {"cpu": "4"}, "conditions": ready}} for i in range(3)]
    dep = {"metadata": {"name": "web", "namespace": "default", "annotations": {}},
           "spec": {"selector": {"matchLabels": {"app": "web"}},
                    "template": {"spec": {"containers": [{"resources": {"limits": {"cpu": "500m"}, "requests": {"cpu": "200m"}}}]}}},
           "status": {"conditions": [{"type": "Progressing", "reason": "NewReplicaSetAvailable"}]}}
    pods = [pod("web-0", "w0", "web"), pod("web-1", "w0", "web"), pod("web-2", "w1", "web"),
            pod("db-0", "w1", "db", req="1000m", lim="2"), pod("big-0", "w2", "big", req="3700m", lim="4"),
            pod("web-3", "w2", "web")]
    st = {"nodes": nodes, "pods": pods, "deployments": [dep], "hpas": [], "used_per_node": "400m",
          "configmaps": [{"metadata": {"name": "omni-security"}, "data": {"hold": hold}}], "jobs": []}
    p = Path(tmp) / "state.json"; p.write_text(json.dumps(st))
    os.environ["FAKE_KUBE_STATE"] = str(p); os.environ["FAKE_KUBE_LOG"] = str(Path(tmp) / "writes.log")
    return p


def limits(p):
    S = json.loads(Path(p).read_text())
    return {q["metadata"]["name"]: (q["spec"]["containers"][0]["resources"]["limits"]["cpu"],
                                    q["spec"]["containers"][0]["resources"]["requests"]["cpu"]) for q in S["pods"]}


def args(tmp):
    a = parser().parse_args(["--kubectl", FAKE, "--audit", str(Path(tmp) / "audit.jsonl"), "--kill-file", str(Path(tmp) / "kill"),
                             "--cap-deployments", "default/web", "--security-configmap", "default/omni-security",
                             "--latency-file", str(Path(tmp) / "latency.csv"), "--mode", "target"])
    return a


def main():
    t = tempfile.mkdtemp(); p = state(t)
    c = Controller(args(t))
    out = c.m.convey({})
    L = limits(p)
    # w0: two serving pods share 0.95 x 4000 = 3800m -> 1900m each; w1: (3800 - 1000) / 1 = 2800m;
    # w2: 3800 - 3700 = 100m < 500m, so the operator's 500m stays
    assert L["web-0"][0] == "1900m" and L["web-1"][0] == "1900m", L
    assert L["web-2"][0] == "2800m", L
    assert L["web-3"][0] == "500m", L
    assert all(L[n][1] == "200m" for n in ("web-0", "web-1", "web-2", "web-3")), "requests untouched"
    assert L["db-0"] == ("2", "1000m") and L["big-0"] == ("4", "3700m"), "other workloads untouched"
    S = json.loads(Path(p).read_text())
    assert S["deployments"][0]["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["cpu"] == "500m", "no rollout"
    assert S["deployments"][0]["metadata"]["annotations"][CPU_ANN] == "500m"
    writes = [json.loads(l) for l in Path(os.environ["FAKE_KUBE_LOG"]).read_text().splitlines()]
    assert all(w[:2] != ["patch", "pod"] or "--subresource" in w for w in writes), "in place only"
    assert c.m.convey({}) == {}, "steady: nothing more to write"
    # the kill switch returns every serving pod to the operator's limit
    (Path(t) / "kill").touch(); c.restore()
    L = limits(p)
    assert all(L[n][0] == "500m" for n in ("web-0", "web-1", "web-2", "web-3")), L
    # a security hold: no expansion
    t2 = tempfile.mkdtemp(); p2 = state(t2, hold="true"); c2 = Controller(args(t2))
    c2.m.convey({"security_block": 1.0})
    assert all(v[0] == "500m" for n, v in limits(p2).items() if n.startswith("web")), "no expansion during a hold"

    # a closed machine still carrying work: in service, not open
    os.environ["FAKE_KUBE_STATE"] = str(p)
    S = json.loads(Path(p).read_text()); S["nodes"][2]["spec"]["unschedulable"] = True; Path(p).write_text(json.dumps(S))
    s = snapshot(Kube(FAKE, audit=lambda r: r), active_only=True)
    assert s["nodes"] == 3 and s["open"] == 2, s
    print("convey: w0 1900m x2, w1 2800m, w2 left at 500m (crowded); requests untouched; no rollout; kill restored 500m; "
          "hold blocks expansion; closed machine with work: in service 3, open 2")
    print("PASS test_convey")


if __name__ == "__main__":
    main()
