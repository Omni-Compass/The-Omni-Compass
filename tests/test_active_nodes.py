"""Full-engine controller options against the fake kubectl: --active-nodes-only ignores cordoned and NoSchedule-tainted
nodes (and the pods and usage on them); without it every Ready node counts; the kill switch runs --node-restore-cmd
exactly once and writes nothing else to the node pool."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Controller, Kube, parser, snapshot
FAKE = str(ROOT / "tests" / "fake_cluster" / "kubectl")


def cluster(tmp):
    ready = [{"type": "Ready", "status": "True"}]
    node = lambda name, spec: {"metadata": {"name": name}, "spec": spec, "status": {"allocatable": {"cpu": "4"}, "conditions": ready}}
    nodes = [node("cp", {"taints": [{"key": "node-role.kubernetes.io/control-plane", "effect": "NoSchedule"}]}),
             node("w1", {}), node("w2", {}), node("w3", {"unschedulable": True})]
    pod = lambda where, cpu, phase="Running": {"status": {"phase": phase}, "spec": {"nodeName": where, "containers": [{"resources": {"requests": {"cpu": cpu}}}]}}
    pods = [pod("cp", "950m"), pod("w1", "500m"), pod("w2", "500m"), {"status": {"phase": "Pending"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "200m"}}}]}}]
    cpu = {"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 50}}}
    hpas = [{"metadata": {"name": "php-apache", "namespace": "default"}, "spec": {"metrics": [cpu]}, "status": {"currentReplicas": 2}}]
    st = Path(tmp) / "state.json"; st.write_text(json.dumps({"nodes": nodes, "pods": pods, "hpas": hpas, "used_per_node": "1000m"}))
    os.environ["FAKE_KUBE_STATE"] = str(st); os.environ["FAKE_KUBE_LOG"] = str(Path(tmp) / "writes.log")


def main():
    t = tempfile.mkdtemp(); cluster(t)
    k = Kube(FAKE, audit=lambda r: r)
    s = snapshot(k, active_only=True)
    assert s["nodes"] == 2 and s["alloc_m"] == 8000, s
    assert s["req_m"] == 1200 and s["used_m"] == 2000 and s["pending"] == 1, s
    # a cordoned worker still carrying work is in service until its work is gone; a DaemonSet pod is not work
    st = Path(os.environ["FAKE_KUBE_STATE"]); S = json.loads(st.read_text())
    S["pods"].append({"metadata": {"ownerReferences": [{"kind": "DaemonSet"}]}, "status": {"phase": "Running"},
                      "spec": {"nodeName": "w3", "containers": [{"resources": {"requests": {"cpu": "100m"}}}]}})
    st.write_text(json.dumps(S)); assert snapshot(k, active_only=True)["nodes"] == 2, "a DaemonSet pod keeps no worker in service"
    S["pods"].append({"metadata": {"ownerReferences": [{"kind": "ReplicaSet"}]}, "status": {"phase": "Running"},
                      "spec": {"nodeName": "w3", "containers": [{"resources": {"requests": {"cpu": "200m"}}}]}})
    st.write_text(json.dumps(S)); s3 = snapshot(k, active_only=True)
    assert s3["nodes"] == 3 and s3["alloc_m"] == 12000, s3
    S["pods"] = S["pods"][:-2]; st.write_text(json.dumps(S))
    s_all = snapshot(k)
    assert s_all["nodes"] == 4 and s_all["req_m"] == 2150 and s_all["used_m"] == 4000, s_all

    marker = Path(t) / "restored"
    a = parser().parse_args(["--kubectl", FAKE, "--mode", "nodepool", "--active-nodes-only", "--interval", "0",
                             "--audit", str(Path(t) / "audit.jsonl"), "--kill-file", str(Path(t) / "kill"),
                             "--node-restore-cmd", f"sh -c 'echo x >> {marker}'"])
    c = Controller(a)
    (Path(t) / "kill").touch()
    for _ in range(3):
        c.step()
    assert marker.read_text().count("x") == 1, "node restore must run exactly once"
    audit = [json.loads(l) for l in (Path(t) / "audit.jsonl").read_text().splitlines()]
    assert sum(1 for r in audit if r.get("why") == "kill switch: restore node pool") == 1
    assert not any(r.get("why") == "node pool size" for r in audit), "no node-pool resize while killed"
    print("active nodes: 2 of 4 counted (control plane and cordoned worker excluded); kill switch restored the node pool once")
    print("PASS test_active_nodes")


if __name__ == "__main__":
    main()
