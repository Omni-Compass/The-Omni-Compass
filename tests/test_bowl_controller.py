# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The bowl law in the live Kubernetes controller (--law bowl), against the fake kubectl (tests/fake_cluster/kubectl).

  calm      p95 far under the SLO: the bowl pulls down, the HPA target never rises above the operator's (never tighter
            than native), and the node pool gives one machine back per decision through the release gate
  hot       p95 past the 0.95 wall: fail up, the HPA target goes to the bottom of its cover (60% of the operator's) at
            once and the node pool asks for one machine more
  blind     no live probe samples: read as past the wall, same as hot
  restore   the kill switch returns every HPA target to the operator's and removes every record
  engine    the six-state engine still runs every decision (E and U in the audit) and the decision names the bowl law
"""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Controller, parser, ANNOTATION
FAKE = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def cluster(tmp, target=50):
    nodes = [{"metadata": {"name": f"n{i}"}, "status": {"allocatable": {"cpu": "4"}, "conditions": [{"type": "Ready", "status": "True"}]}}
             for i in range(6)]
    pods = [{"status": {"phase": "Running"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "200m"}}}]}} for _ in range(3)]
    cpu = {"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": target}}}
    cur = [{"type": "Resource", "resource": {"name": "cpu", "current": {"averageUtilization": 40}}}]
    hpas = [{"metadata": {"name": "web", "namespace": "default"}, "spec": {"minReplicas": 1, "maxReplicas": 10, "metrics": [cpu]},
             "status": {"currentReplicas": 3, "desiredReplicas": 3, "currentMetrics": cur}}]
    st = Path(tmp) / "state.json"; st.write_text(json.dumps({"nodes": nodes, "pods": pods, "hpas": hpas, "used_per_node": "300m"}))
    os.environ["FAKE_KUBE_STATE"] = str(st); os.environ["FAKE_KUBE_LOG"] = str(Path(tmp) / "writes.log")
    return st


def probe(tmp, ms, n=40):
    p = Path(tmp) / "latency.csv"
    rows = ["elapsed_seconds,latency_ms,ok"] + [f"{i * 0.5},{ms},1" for i in range(n)]
    p.write_text("\n".join(rows) + "\n"); os.utime(p, None)
    return p


def controller(tmp, lat, *extra):
    marker = Path(tmp) / "scaled"
    cmd = f"python3 -c \"open('{marker}', 'a').write('{{n}}\\\\n')\""
    a = parser().parse_args(["--kubectl", FAKE, "--interval", "60", "--audit", str(Path(tmp) / "audit.jsonl"),
                             "--kill-file", str(Path(tmp) / "kill"), "--mode", "nodepool", "--law", "bowl",
                             "--node-scale-cmd", cmd, "--max-node-step", "1", "--latency-file", str(lat), "--slo-ms", "500",
                             "--latency-window-s", "30", *extra])
    return Controller(a), marker


def target_now(st):
    return json.loads(st.read_text())["hpas"][0]["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"]


def decisions(tmp):
    return [json.loads(l)["decision"] for l in (Path(tmp) / "audit.jsonl").read_text().splitlines() if '"decision"' in l
            and isinstance(json.loads(l).get("decision"), dict)]


def main():
    # calm: p95 = 50 ms on a 500 ms SLO (position 0.1)
    t = tempfile.mkdtemp(); st = cluster(t); lat = probe(t, 50.0)
    c, marker = controller(t, lat)
    for _ in range(6):
        c.step()
    ns = [int(x) for x in marker.read_text().split()] if marker.exists() else []
    d = decisions(t)
    assert all(x["law"] == "bowl" and x["bowl"] is not None for x in d), "decision does not name the bowl law"
    assert all("E" in x and "U" in x for x in d), "the engine did not run"
    assert target_now(st) <= 50, "the bowl tightened the HPA past the operator's target"
    assert all(b - a in (-1, 0) for a, b in zip([6] + ns, ns)), f"more than one machine back per decision: {ns}"
    print(f"calm: target {target_now(st)} (operator 50, never higher), node commands {ns}, "
          f"force {d[-1]['bowl']['force']}, position {d[-1]['bowl']['position']}")

    # hot: p95 = 600 ms (position 1.2, past the wall): fail up at once
    t = tempfile.mkdtemp(); st = cluster(t); lat = probe(t, 600.0)
    c, marker = controller(t, lat)
    c.step()
    ns = [int(x) for x in marker.read_text().split()] if marker.exists() else []
    assert target_now(st) == 30, f"fail up: target {target_now(st)}, expected the cover's bottom 30"
    assert ns and ns[-1] == 7 or c.a.max_nodes < 7, f"fail up: node commands {ns}"
    print(f"hot: target 50 -> {target_now(st)} at once (fail up), node command {ns}")

    # the fault is over: responses back inside the band, nothing waiting. The operator's own target returns at once,
    # inside the autoscaler's window, so the extra pods last only as long as the fault
    lat = probe(t, 50.0)
    for k in range(1, 4):
        c.step()
        if target_now(st) == 50:
            break
    assert target_now(st) == 50, f"fault over: target {target_now(st)}, expected the operator's 50 back at once"
    print(f"fault over: target back to 50 after {k} decision(s), inside the autoscaler's window")

    # blind: a probe file older than twice its window reads as past the wall: fail up, but more pods cannot answer a
    # blind sense, so the HPA target stays the operator's own (as on the card, fail up is native's own settings)
    t = tempfile.mkdtemp(); st = cluster(t); lat = probe(t, 50.0)
    old = time.time() - 600; os.utime(lat, (old, old))
    c, marker = controller(t, lat)
    c.step()
    assert target_now(st) == 50, f"blind: target {target_now(st)}, expected the operator's own 50"
    assert decisions(t)[-1]["bowl"]["position"] >= 0.95, "blind did not read as past the wall"
    print(f"blind: past the wall, target stays the operator's {target_now(st)} (more pods cannot answer a blind sense)")

    # restore: the kill switch hands the target back and removes the record (after a real breach moved it)
    t = tempfile.mkdtemp(); st = cluster(t); lat = probe(t, 600.0)
    c, marker = controller(t, lat); c.step()
    assert target_now(st) == 30
    (Path(t) / "kill").write_text("1")
    c.step()
    S = json.loads(st.read_text())
    assert target_now(st) == 50 and ANNOTATION not in S["hpas"][0]["metadata"].get("annotations", {})
    print("kill switch: target back to 50, no record left")
    print("PASS bowl law in the live controller")


if __name__ == "__main__":
    main()
