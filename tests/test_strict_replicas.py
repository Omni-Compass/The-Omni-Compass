# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Strict C on the fake cluster: Omni-Compass sets the replica count from measured utilisation (up at once, down only to
the highest recent recommendation), sets it as the HPA's floor within the HPA's own range (growth stays free up to the
operator's maximum), and the kill switch restores the range and leaves no record."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Controller, parser, RANGE_ANN
FAKE = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def main():
    t = Path(tempfile.mkdtemp())
    st = {"nodes": [{"metadata": {"name": "w0"}, "spec": {}, "status": {"allocatable": {"cpu": "8"}, "conditions": [{"type": "Ready", "status": "True"}]}}],
          "pods": [], "used_per_node": "1000m", "deployments": [], "configmaps": [], "jobs": [],
          "hpas": [{"metadata": {"name": "web", "namespace": "default"},
                    "spec": {"minReplicas": 1, "maxReplicas": 10, "metrics": [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 50}}}]},
                    "status": {"currentReplicas": 2, "currentMetrics": [{"type": "Resource", "resource": {"name": "cpu", "current": {"averageUtilization": 150}}}]}}]}
    p = t / "state.json"; p.write_text(json.dumps(st)); os.environ["FAKE_KUBE_STATE"] = str(p); os.environ["FAKE_KUBE_LOG"] = str(t / "w.log")
    a = parser().parse_args(["--kubectl", FAKE, "--mode", "target", "--strict-replicas", "--interval", "0", "--audit", str(t / "a.jsonl"), "--kill-file", str(t / "kill")])
    c = Controller(a)
    hpa = lambda: json.loads(p.read_text())["hpas"][0]
    c.step(); assert (hpa()["spec"]["minReplicas"], hpa()["spec"]["maxReplicas"]) == (6, 10), hpa()["spec"]   # 2 x 150/50; the max stays free
    assert hpa()["metadata"]["annotations"][RANGE_ANN] == "1,10"
    s = json.loads(p.read_text()); s["hpas"][0]["status"] = {"currentReplicas": 6, "currentMetrics": [{"type": "Resource", "resource": {"name": "cpu", "current": {"averageUtilization": 20}}}]}
    p.write_text(json.dumps(s))
    c.step(); assert hpa()["spec"]["minReplicas"] == 6, "down only to the highest recent recommendation"
    for _ in range(5):
        c.step()
    assert hpa()["spec"]["minReplicas"] == 3, hpa()["spec"]          # 6 x 20/50 = 2.4 -> 3 once the window has passed
    (t / "kill").touch(); c.step()
    assert (hpa()["spec"]["minReplicas"], hpa()["spec"]["maxReplicas"]) == (1, 10) and RANGE_ANN not in hpa()["metadata"].get("annotations", {})
    print("PASS test_strict_replicas")


if __name__ == "__main__":
    main()
