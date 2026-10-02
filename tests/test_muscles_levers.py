# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The five added live levers against the fake kubectl: rightsize sets pod CPU requests from use in place and the kill
switch restores them; coldstart scales an idle deployment to zero and wakes it when work waits; batch_pace pauses a
pausable Job under power stress and resumes it when calm; contain puts a quota and scaled limits on an agent namespace
over budget and lifts them; the cooling connector moves the setpoint with heat and the kill switch restores it."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Kube, parser
from omni_controller.muscles import Muscles, REQ_ANN, REPL_ANN, PACE_ANN
FAKE = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def setup(tmp, queue="0"):
    res = {"limits": {"cpu": "1000m"}, "requests": {"cpu": "500m"}}
    dep = lambda name, rep=2: {"metadata": {"name": name, "namespace": "default", "annotations": {}},
                               "spec": {"replicas": rep, "selector": {"matchLabels": {"app": name}},
                                        "template": {"spec": {"containers": [{"resources": json.loads(json.dumps(res))}]}}},
                               "status": {"conditions": []}}
    pod = lambda n, app, ns="default", use="100m", lim="1000m": {
        "metadata": {"name": n, "namespace": ns, "labels": {"app": app}}, "status": {"phase": "Running"}, "usage": use,
        "spec": {"nodeName": "w0", "containers": [{"resources": {"limits": {"cpu": lim}, "requests": {"cpu": "500m"}}}]}}
    job = lambda n, susp: {"metadata": {"name": n, "namespace": "train", "labels": {"omnicompass.io/pausable": "true"}},
                           "spec": {"suspend": susp}}
    st = {"nodes": [], "pods": [pod("web-0", "web", use="100m"), pod("web-1", "web", use="300m"),
                                pod("agent-0", "agent", ns="agents", use="900m", lim="1000m"),
                                pod("agent-1", "agent", ns="agents", use="900m", lim="1000m")],
          "deployments": [dep("web"), dep("svc", 3)], "hpas": [], "used_per_node": "0m",
          "configmaps": [{"metadata": {"name": "work"}, "data": {"queue": queue}}], "jobs": [job("train-a", False)]}
    p = Path(tmp) / "state.json"; p.write_text(json.dumps(st))
    os.environ["FAKE_KUBE_STATE"] = str(p); os.environ["FAKE_KUBE_LOG"] = str(Path(tmp) / "writes.log")
    return p


def load(p): return json.loads(Path(p).read_text())


def main():
    t = tempfile.mkdtemp(); p = setup(t)
    cool = Path(t) / "bms.log"
    a = parser().parse_args(["--kubectl", FAKE, "--audit", str(Path(t) / "audit.jsonl"),
                             "--rightsize-deployments", "default/web", "--coldstart-deployments", "default/svc",
                             "--coldstart-signal", "default/work", "--coldstart-idle", "2", "--batch-pace",
                             "--contain-namespaces", "agents", "--contain-cpu-m", "1000",
                             "--cooling-cmd", f"sh -c 'echo {{c}} >> {cool}'"])
    rec = []
    m = Muscles(Kube(FAKE, audit=rec.append), a, rec.append)
    calm = {"power_stress": 0.5, "thermal": 0.5, "security_block": 0.0, "slo_clean": True}
    m.push({"power_cap": 1.0, "change_permitted": True, "rollback_authorized": False}, calm)
    req = {q["metadata"]["name"]: q["spec"]["containers"][0]["resources"]["requests"]["cpu"] for q in load(p)["pods"] if q["metadata"]["labels"]["app"] == "web"}
    assert req == {"web-0": "130m", "web-1": "390m"}, req                         # use x 1.3, in place
    assert next(d for d in load(p)["deployments"] if d["metadata"]["name"] == "web")["metadata"]["annotations"][REQ_ANN] == "500m"
    q = load(p)["quotas"]; assert [(x["name"], x["namespace"], x["hard"]) for x in q] == [("omni-containment", "agents", "limits.cpu=1000m")], q
    assert json.loads(q[0]["annotations"]["omnicompass.io/original-limits"]) == {"agent-0": "1000m", "agent-1": "1000m"}
    lims = [q["spec"]["containers"][0]["resources"]["limits"]["cpu"] for q in load(p)["pods"] if q["metadata"].get("namespace") == "agents"]
    assert lims == ["500m", "500m"], lims                                          # 1800m use -> equal share of 1000m
    assert cool.read_text().split() == ["27.0"], cool.read_text()                 # cool: warm setpoint, chiller saves
    svc = lambda: next(d for d in load(p)["deployments"] if d["metadata"]["name"] == "svc")
    assert svc()["spec"]["replicas"] == 3                                          # idle 1 decision: not yet
    hot = dict(calm, power_stress=1.0, thermal=0.95)
    m.push({"power_cap": 1.0, "change_permitted": True, "rollback_authorized": False}, hot)
    assert svc()["spec"]["replicas"] == 0 and svc()["metadata"]["annotations"][REPL_ANN] == "3"   # idle 2: scaled to zero
    j = load(p)["jobs"][0]; assert j["spec"]["suspend"] is True and j["metadata"]["annotations"][PACE_ANN] == "true"
    assert cool.read_text().split()[-1] == "18.9", cool.read_text()               # hot: cold setpoint
    s = load(p); s["configmaps"][0]["data"]["queue"] = "5"
    for q in s["pods"]:
        if q["metadata"].get("namespace") == "agents": q["usage"] = "200m"
    Path(p).write_text(json.dumps(s))
    m.push({"power_cap": 1.0, "change_permitted": True, "rollback_authorized": False}, calm)
    assert svc()["spec"]["replicas"] == 3                                          # work waiting: woken
    assert load(p)["jobs"][0]["spec"]["suspend"] is False                          # calm: resumed
    assert load(p).get("quotas") == [], "containment lifted when back under budget"
    lims = [q["spec"]["containers"][0]["resources"]["limits"]["cpu"] for q in load(p)["pods"] if q["metadata"].get("namespace") == "agents"]
    assert lims == ["1000m", "1000m"], lims
    # kill switch restores everything
    s = load(p); s["configmaps"][0]["data"]["queue"] = "0"; Path(p).write_text(json.dumps(s))
    for _ in range(3):
        m.push({"power_cap": 1.0, "change_permitted": True, "rollback_authorized": False}, hot)
    assert svc()["spec"]["replicas"] == 0 and load(p)["jobs"][0]["spec"]["suspend"] is True
    # containment again, then the kill switch from a fresh process (records live in the cluster, not in memory)
    s = load(p)
    for q in s["pods"]:
        if q["metadata"].get("namespace") == "agents": q["usage"] = "900m"
    Path(p).write_text(json.dumps(s))
    m.push({"power_cap": 1.0, "change_permitted": True, "rollback_authorized": False}, hot)
    assert load(p)["quotas"], "contained again"
    m = Muscles(Kube(FAKE, audit=rec.append), a, rec.append)
    m._setpoint = 18.9
    m.restore()
    assert load(p).get("quotas") == [], "kill switch from a fresh process deletes the quota"
    lims = [q["spec"]["containers"][0]["resources"]["limits"]["cpu"] for q in load(p)["pods"] if q["metadata"].get("namespace") == "agents"]
    assert lims == ["1000m", "1000m"], lims
    assert svc()["spec"]["replicas"] == 3 and REPL_ANN not in svc()["metadata"]["annotations"]
    assert load(p)["jobs"][0]["spec"]["suspend"] is False
    req = {q["spec"]["containers"][0]["resources"]["requests"]["cpu"] for q in load(p)["pods"] if q["metadata"]["labels"]["app"] == "web"}
    assert req == {"500m"}, req
    assert cool.read_text().split()[-1] == "22.0"
    assert all("why" in r for r in rec if "write" in r)
    print("levers: rightsize, coldstart, batch pace, containment, cooling; kill restores every one")
    print("PASS test_muscles_levers")


if __name__ == "__main__":
    main()
