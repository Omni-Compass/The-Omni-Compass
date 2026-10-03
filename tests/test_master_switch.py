# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The master switch (omnicompass/master.py, tools/omni_switch.py): one OFF for the whole harness.

Two governors run at once as their own processes, against the stand-in hardware: the two-wire GPU governor on the fake
nvidia-smi, and the Kubernetes controller (bowl law, HPA target mode) on the fake kubectl. Then:

  running   both register themselves; status lists both
  off       one command turns the whole harness off: both governors put every setting back (the card's start limit and
            clocks, the operator's HPA target) and exit, within seconds
  refused   while the switch is OFF, neither governor will start (no authority taken)
  on        after ON, a governor starts again
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
SMI = str(ROOT / "tests" / "fake_gpu" / "nvidia-smi")
KUBECTL = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def main():
    t = Path(tempfile.mkdtemp())
    env = dict(os.environ, OMNI_MASTER_OFF=str(t / "switch" / "OFF"), PYTHONPATH=str(ROOT))
    # the card: busy, its limit 150 W
    smi = t / "smi.json"
    smi.write_text(json.dumps({"limit": {"0": 150.0}, "default": 150.0, "min": 100.0, "max": 150.0, "draw_w": 120.0,
                               "util": 60, "temp": 60, "clock_top": 1695.0, "busy_clock": 1200.0}))
    lat = t / "latency.csv"
    lat.write_text("elapsed_seconds,latency_ms,ok,service_ms\n" + "".join(f"{i * 0.2},100,1,20\n" for i in range(50)))
    # the cluster: one HPA at the operator's target 50
    cpu = {"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 50}}}
    kube = t / "kube.json"
    kube.write_text(json.dumps({
        "nodes": [{"metadata": {"name": f"n{i}"}, "status": {"allocatable": {"cpu": "4"},
                   "conditions": [{"type": "Ready", "status": "True"}]}} for i in range(4)],
        "pods": [{"status": {"phase": "Running"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "200m"}}}]}}],
        "hpas": [{"metadata": {"name": "web", "namespace": "default"}, "spec": {"minReplicas": 1, "maxReplicas": 10, "metrics": [cpu]},
                  "status": {"currentReplicas": 3, "desiredReplicas": 3,
                             "currentMetrics": [{"type": "Resource", "resource": {"name": "cpu", "current": {"averageUtilization": 40}}}]}}],
        "used_per_node": "300m"}))
    env.update(FAKE_SMI_STATE=str(smi), FAKE_KUBE_STATE=str(kube), FAKE_KUBE_LOG=str(t / "kube_writes.log"))
    hot = t / "hot.csv"
    hot.write_text("elapsed_seconds,latency_ms,ok\n" + "".join(f"{i * 0.5},900,1\n" for i in range(40)))
    gpu_cmd = [sys.executable, "-m", "omni_controller.gpu_bowl", "--mode", "cap", "--smi", SMI, "--interval", "0.5",
               "--audit", str(t / "gpu.jsonl"), "--kill-file", str(t / "gpu.kill"), "--latency-file", str(lat),
               "--slo-ms", "800", "--floor-w", "105", "--learn-samples", "3"]
    k8s_cmd = [sys.executable, "-m", "omni_controller.controller", "--kubectl", KUBECTL, "--interval", "1",
               "--audit", str(t / "k8s.jsonl"), "--kill-file", str(t / "k8s.kill"), "--mode", "target", "--law", "bowl",
               "--latency-file", str(hot), "--slo-ms", "500", "--latency-window-s", "30"]
    switch = [sys.executable, str(ROOT / "tools" / "omni_switch.py")]
    gpu = subprocess.Popen(gpu_cmd, env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    k8s = subprocess.Popen(k8s_cmd, env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    target = lambda: json.loads(kube.read_text())["hpas"][0]["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"]
    t0 = time.time()
    while time.time() - t0 < 30 and (target() == 50 or not (t / "gpu.jsonl").exists()):
        time.sleep(0.5)
    assert target() < 50, "the controller never acted (the hot probe should have tightened the HPA target)"
    st = subprocess.run(switch + ["status"], env=env, capture_output=True, text=True).stdout
    assert "kubernetes controller" in st and "GPU governor (two wires)" in st and "ON" in st, st
    # OFF: the whole harness at once
    r = subprocess.run(switch + ["off", "--reason", "test", "--wait", "30"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert gpu.wait(10) is not None and k8s.wait(10) is not None
    assert target() == 50, f"HPA target not handed back: {target()}"
    g = [json.loads(l) for l in (t / "gpu.jsonl").read_text().splitlines()]
    rest = [x for x in g if "restored" in x]
    assert rest and rest[-1]["ok"] and json.loads(smi.read_text())["limit"]["0"] == 150.0, "card not handed back"
    k = (t / "k8s.jsonl").read_text()
    assert "master switch: OFF" in k
    st = subprocess.run(switch + ["status"], env=env, capture_output=True, text=True).stdout
    assert "OFF" in st and "running:" not in st, st
    # refused while OFF
    for cmd in (gpu_cmd, k8s_cmd):
        p = subprocess.run(cmd, env=env, cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert p.returncode != 0 and "master switch is OFF" in p.stderr, p.stderr[-300:]
    # ON: a governor starts again
    subprocess.run(switch + ["on"], env=env, check=True, capture_output=True)
    p = subprocess.run(k8s_cmd + ["--iterations", "1"], env=env, cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-300:]
    print("PASS master switch: one OFF stops every governor at once, every setting handed back (card limit and clocks, "
          "HPA target), nothing starts while OFF, ON allows a start again")


if __name__ == "__main__":
    main()
