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
    # the replica organ reads the gain: mean conveyed limit / operator's limit = (1900 + 1900 + 2800 + 500) / 4 / 500
    g = c.m.gain[("default", "web")]
    assert abs(g - 3.55) < 1e-9, g
    hpa = {"metadata": {"namespace": "default", "name": "web"}, "spec": {"scaleTargetRef": {"kind": "Deployment", "name": "web"}}}
    assert abs(c._gain(hpa) - 3.55) < 1e-9 and c._gain({"metadata": {"namespace": "x", "name": "y"}, "spec": {}}) == 1.0
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
    # closed by the prefer-not idle mark instead of a cordon: the same accounting; empty, it idles
    S["nodes"][2]["spec"].pop("unschedulable"); S["nodes"][2]["spec"]["taints"] = [{"key": "omnicompass.io/idle", "value": "true", "effect": "PreferNoSchedule"}]
    Path(p).write_text(json.dumps(S)); s = snapshot(Kube(FAKE, audit=lambda r: r), active_only=True)
    assert s["nodes"] == 3 and s["open"] == 2, s
    S["pods"] = [q for q in S["pods"] if q["spec"]["nodeName"] != "w2"]; Path(p).write_text(json.dumps(S))
    s = snapshot(Kube(FAKE, audit=lambda r: r), active_only=True)
    assert s["nodes"] == 2 and s["open"] == 2, s
    # on top, with response time clean: the HPA target keeps the operator's promise in queue terms at the CPU each pod
    # is guaranteed: the autoscaler's largest count (10) over the 3 machines in service is 4 pods a machine, 0.95 x 4000m
    # / 4 = 950m, g = 1.9 (below the momentary mean 3.55), so 50% -> 95%; while response time is not yet clean (the
    # first decisions), the operator's own 50% stands
    t3 = tempfile.mkdtemp(); p3 = state(t3); S = json.loads(Path(p3).read_text())
    S["hpas"] = [{"metadata": {"name": "web", "namespace": "default"}, "spec": {"minReplicas": 1, "maxReplicas": 10,
                  "scaleTargetRef": {"kind": "Deployment", "name": "web"}, "metrics": [{"type": "Resource", "resource": {
                      "name": "cpu", "target": {"type": "Utilization", "averageUtilization": 50}}}]},
                  "status": {"currentReplicas": 4, "desiredReplicas": 4}}]
    Path(p3).write_text(json.dumps(S))
    lf = Path(t3) / "latency.csv"; lf.write_text("elapsed_seconds,latency_ms,ok\n" + "".join(f"{i},100,1\n" for i in range(60)))
    c3 = Controller(args(t3)); c3.a.slo_ms = 500.0; c3.a.convey_on = 0.0; seen = []   # conveying always
    for _ in range(4):
        os.utime(lf); c3.step()
        seen.append(json.loads(Path(p3).read_text())["hpas"][0]["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"])
    assert seen[0] == 50 and seen[-1] == 95, seen
    # the muscle's own clock: a new target inside the autoscaler's scale-down window (300 s) is held back; after it,
    # the target follows. A machine leaving service changes the guaranteed share (10 over 2 machines: 5 a machine,
    # 760m, g 1.52 -> 76%)
    S3 = json.loads(Path(p3).read_text()); S3["nodes"] = S3["nodes"][:2]
    S3["pods"] = [q for q in S3["pods"] if q["spec"]["nodeName"] in ("w0", "w1")]; Path(p3).write_text(json.dumps(S3))
    os.utime(lf); c3.step()
    held = json.loads(Path(p3).read_text())["hpas"][0]["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"]
    assert held == 95, held
    c3.target_at = {k: v - 301 for k, v in c3.target_at.items()}; os.utime(lf); c3.step()
    moved = json.loads(Path(p3).read_text())["hpas"][0]["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"]
    assert moved == 76, moved
    # only when needed: with an SLO of 500 ms, conveyance engages at p95 >= 250 ms (convey-on 0.5), holds down to
    # 125 ms (convey-off 0.25), and below that every serving pod returns to the operator's 500m; blind engages
    t4 = tempfile.mkdtemp(); p4 = state(t4); c4 = Controller(args(t4)); c4.a.slo_ms = 500.0
    assert (c4.a.convey_on, c4.a.convey_off) == (0.5, 0.25), (c4.a.convey_on, c4.a.convey_off)
    lf4 = Path(t4) / "latency.csv"
    def probe(ms):
        lf4.write_text("elapsed_seconds,latency_ms,ok\n" + "".join(f"{i},{ms},1\n" for i in range(60)))
    web = lambda: [limits(p4)[n][0] for n in ("web-0", "web-1", "web-2")]
    probe(100); c4.m.convey({})
    assert web() == ["500m"] * 3 and c4.m.gain[("default", "web")] == 1.0, "calm: the operator's limit, gain 1"
    probe(300); c4.m.convey({})
    assert web() == ["1900m", "1900m", "2800m"], "p95 over half the SLO: idle CPU conveyed"
    probe(150); c4.m.convey({})
    assert web() == ["1900m", "1900m", "2800m"], "inside the band: still conveying"
    probe(100); c4.m.convey({})
    assert web() == ["500m"] * 3, "calm again: back to the operator's limit"
    lf4.unlink(); c4.m.convey({})
    assert web() == ["1900m", "1900m", "2800m"], "blind: service first, conveyed"
    ev = [json.loads(l) for l in (Path(t4) / "audit.jsonl").read_text().splitlines() if '"convey"' in l]
    assert [e["convey"] for e in ev if e.get("convey") in ("engaged", "released")] == ["engaged", "released", "engaged"], ev
    print("convey: w0 1900m x2, w1 2800m, w2 left at 500m (crowded); requests untouched; no rollout; kill restored 500m; "
          "only when needed: calm 500m, p95 300 ms conveys, 150 ms holds, 100 ms returns 500m, blind conveys; "
          "hold blocks expansion; HPA target 50 -> 95 once clean (the guaranteed share, same queue promise), held for the autoscaler's window, then 76; closed machine with work: in service 3, open 2")
    print("PASS test_convey")


if __name__ == "__main__":
    main()
