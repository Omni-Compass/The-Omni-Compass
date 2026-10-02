# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Walk the live controller (omni_controller/controller.py, nodepool mode, closure law, two-way nervous system) through
five situations on the repository's stand-in cluster (tests/fake_cluster/kubectl: answers like the Kubernetes API from a
JSON state file; no pods run). Prints the decision trail each decision writes to its audit:
  1 calm, machines idle            -> releases one machine per decision down to the floor (3 here)
  2 latency breached now           -> holds ("latency breached now")
  3 the latency probe freezes      -> holds ("a sense is blind"; the engine's stale channel rises)
  4 a drain is refused (order does not land) -> next decision holds ("last node command did not land")
  5 pods scale up                  -> holds ("pods scaling up")
Usage: python tools/demo_nervous_system.py  ->  results/local_run/NERVOUS_SYSTEM_DEMO.txt"""
import csv, json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Controller, parser
FAKE = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def main():
    t = Path(tempfile.mkdtemp()); p = t / "state.json"; lat = t / "latency.csv"; out = []
    nodes = [{"metadata": {"name": f"w{i}"}, "spec": {}, "status": {"allocatable": {"cpu": "4"},
             "conditions": [{"type": "Ready", "status": "True"}]}} for i in range(6)]
    hpa = {"metadata": {"name": "web", "namespace": "default"},
           "spec": {"minReplicas": 1, "maxReplicas": 10, "metrics": [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 50}}}]},
           "status": {"currentReplicas": 2, "desiredReplicas": 2, "currentMetrics": [{"type": "Resource", "resource": {"name": "cpu", "current": {"averageUtilization": 30}}}]}}
    p.write_text(json.dumps({"nodes": nodes, "pods": [], "used_per_node": "300m", "deployments": [], "configmaps": [], "jobs": [], "hpas": [hpa]}))
    os.environ["FAKE_KUBE_STATE"] = str(p); os.environ["FAKE_KUBE_LOG"] = str(t / "w.log")
    scale = t / "scale.py"   # node-pool actuator: cordon down to n (refuses when REFUSE_DRAIN exists)
    scale.write_text(f'''import json, os, sys
n = int(sys.argv[1]); s = json.load(open({str(p)!r}))
if os.path.exists({str(t / "REFUSE_DRAIN")!r}): sys.exit(0)
for i, nd in enumerate(s["nodes"]): nd["spec"]["unschedulable"] = i >= n
json.dump(s, open({str(p)!r}, "w"))''')

    def probe(ms, fresh=True):
        with open(lat, "w") as f:
            w = csv.writer(f); w.writerow(["elapsed_seconds", "latency_ms", "ok"]); w.writerows((s, ms, 1) for s in range(0, 120))
        if not fresh:
            old = time.time() - 900; os.utime(lat, (old, old))

    probe(200)
    a = parser().parse_args(["--kubectl", FAKE, "--mode", "nodepool", "--active-nodes-only", "--interval", "0", "--min-nodes", "3",
                             "--max-nodes", "6", "--node-scale-cmd", f"{sys.executable} {scale} {{n}}", "--latency-file", str(lat),
                             "--slo-ms", "500", "--slo-clear", "1", "--audit", str(t / "a.jsonl"), "--kill-file", str(t / "kill"),
                             "--closure", str(ROOT / "tuning/GLOBAL_LEAGUE_PREREGISTRATION.json")])
    c = Controller(a)

    def step(label):
        c.step()
        recs = [json.loads(l) for l in open(t / "a.jsonl")]
        auth = [r for r in recs if "authority" in r][-1]["authority"]; dec = [r for r in recs if isinstance(r.get("decision"), dict)][-1]["decision"]
        line = (f"{label:34s} machines {dec['nodes_observed']} -> {dec['nodes_recommended']} | gate: {auth['node_gate']['reason']} | "
                f"node calm {auth['node_view']['calm']} | blind {[k for k, v in auth['senses']['blind'].items() if v]} | "
                f"proprioception {auth['proprioception']}")
        print(line); out.append(line)

    for i in range(5):
        step(f"1 calm, idle machines (decision {i + 1})")
    s = json.loads(p.read_text())                      # release the floor's grip for scenario 4: one spare machine back
    for nd in s["nodes"][:4]: nd["spec"]["unschedulable"] = False
    p.write_text(json.dumps(s))
    probe(900); step("2 latency breached now (p95 900 ms)")
    probe(200, fresh=False); step("3 latency probe frozen (15 min old)")
    probe(200); (t / "REFUSE_DRAIN").touch()
    for i in range(3):
        step(f"4 drain refused (decision {i + 1})")
    (t / "REFUSE_DRAIN").unlink()
    s = json.loads(p.read_text()); s["hpas"][0]["status"]["desiredReplicas"] = 5; p.write_text(json.dumps(s))
    step("5 pods scaling up (HPA 2 -> 5)")
    Path(ROOT / "results/local_run").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/local_run/NERVOUS_SYSTEM_DEMO.txt").write_text(
        "Live controller on the stand-in cluster (fake kubectl; no pods run). Decision trail as written to the audit.\n\n" + "\n".join(out) + "\n")


if __name__ == "__main__":
    main()
