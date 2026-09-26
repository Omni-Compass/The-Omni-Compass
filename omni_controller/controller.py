"""Omni-Compass live controller for a real Kubernetes cluster.

Modes
  observe   read the cluster every interval, run the fleet-mode governor in OBSERVE, log every decision; no writes (default)
  target    additionally patch each HPA's CPU averageUtilization to rho* (bounded, rate-limited); the Cluster Autoscaler and
            all node management remain unchanged
  nodepool  additionally size one node pool to the governor's recommendation through --node-scale-cmd, a command template
            such as "aws autoscaling set-desired-capacity --auto-scaling-group-name POOL --desired-capacity {n}"; the
            Cluster Autoscaler must not manage that pool
Safety
  every node action passes through the shield (bounds, step limit); the recommendation never falls below what the CPU
  requests of running and pending pods, or current usage, need, and capacity required by that floor is added in one step
  (the step limit applies only to the governor's own adjustments); --dry-run logs intended writes without executing them; creating the kill file (or
  setting OMNI_KILL=1) restores every HPA target this controller changed, runs --node-restore-cmd if given, and returns to
  observe; every decision and action
  is appended to the audit log.
Requires kubectl on PATH with access to the cluster (metrics-server for kubectl top).
"""
from __future__ import annotations

import argparse, json, math, os, shlex, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass.adapter import Governor, mode_law, OBSERVE
from omnicompass.shield import enforce, ShieldLimits

ANNOTATION = "omnicompass.io/original-target-utilization"


def to_milli(v: str) -> float:
    v = str(v).strip()
    if v.endswith("m"):
        return float(v[:-1])
    if v.endswith("n"):
        return float(v[:-1]) / 1e6
    return float(v) * 1000.0


class Kube:
    def __init__(self, kubectl: str = "kubectl", dry_run: bool = False, audit=None):
        self.kubectl, self.dry_run, self.audit = kubectl, dry_run, audit

    def get(self, *args):
        out = subprocess.run([self.kubectl, *args], capture_output=True, text=True, check=True).stdout
        return json.loads(out) if "-o" in args and "json" in args else out

    def write(self, args, why):
        self.audit({"write": [self.kubectl, *args], "why": why, "dry_run": self.dry_run})
        if not self.dry_run:
            subprocess.run([self.kubectl, *args], capture_output=True, text=True, check=True)


def schedulable(n):
    """False for a cordoned node or one tainted NoSchedule (control plane, or a node the node pool has parked)."""
    spec = n.get("spec", {})
    return not spec.get("unschedulable") and not any(t.get("effect") == "NoSchedule" for t in spec.get("taints") or [])


def snapshot(k: Kube, active_only: bool = False):
    nodes = k.get("get", "nodes", "-o", "json")["items"]
    ready = [n for n in nodes if any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"].get("conditions", []))]
    if active_only:
        ready = [n for n in ready if schedulable(n)]
    names = {n["metadata"]["name"] for n in ready}
    alloc = sum(to_milli(n["status"]["allocatable"]["cpu"]) for n in ready)
    pods = k.get("get", "pods", "-A", "-o", "json")["items"]
    req = sum(to_milli(c.get("resources", {}).get("requests", {}).get("cpu", "0")) for p in pods
              if p["status"].get("phase") in ("Running", "Pending")
              and (not active_only or p["status"].get("phase") == "Pending" or p["spec"].get("nodeName") in names)
              for c in p["spec"]["containers"])
    pending = sum(1 for p in pods if p["status"].get("phase") == "Pending")
    top = k.get("top", "nodes", "--no-headers")
    used = sum(to_milli(line.split()[1]) for line in top.strip().splitlines()
               if line.strip() and (not active_only or line.split()[0] in names))
    hpas = k.get("get", "hpa", "-A", "-o", "json")["items"]
    return {"nodes": len(ready), "alloc_m": alloc, "req_m": req, "used_m": used, "pending": pending, "hpas": hpas}


def cpu_target(h):
    for i, m in enumerate(h["spec"].get("metrics", [])):
        if m.get("type") == "Resource" and m["resource"]["name"] == "cpu" and "averageUtilization" in m["resource"]["target"]:
            return i, int(m["resource"]["target"]["averageUtilization"])
    return None, None


class Controller:
    def __init__(self, a, kube: Kube | None = None):
        self.a = a
        self.log = open(a.audit, "a") if a.audit else None
        self.k = kube or Kube(a.kubectl, a.dry_run, self.audit)
        self.k.audit = self.audit
        self.g = Governor(law=mode_law("fleet")); self.g.set_mode(OBSERVE)
        self.rec_n = None
        self.changed = {}
        self.nodes_restored = False

    def audit(self, rec):
        rec = {"time": time.time(), **rec}
        if self.log:
            self.log.write(json.dumps(rec) + "\n"); self.log.flush()
        return rec

    def killed(self):
        return os.environ.get("OMNI_KILL") == "1" or (self.a.kill_file and Path(self.a.kill_file).exists())

    def restore(self):
        for h in self.k.get("get", "hpa", "-A", "-o", "json")["items"]:
            orig = h["metadata"].get("annotations", {}).get(ANNOTATION)
            if orig is None:
                continue
            ns, name = h["metadata"]["namespace"], h["metadata"]["name"]
            idx, _ = cpu_target(h)
            if idx is not None:
                self.k.write(["patch", "hpa", name, "-n", ns, "--type=json", "-p",
                              json.dumps([{"op": "replace", "path": f"/spec/metrics/{idx}/resource/target/averageUtilization", "value": int(orig)}])],
                             "kill switch: restore original HPA target")
            self.k.write(["annotate", "hpa", name, "-n", ns, f"{ANNOTATION}-"], "kill switch: remove record")
        self.changed.clear()
        cmd = getattr(self.a, "node_restore_cmd", "")
        if cmd and not self.nodes_restored:
            self.audit({"write": shlex.split(cmd), "why": "kill switch: restore node pool", "dry_run": self.a.dry_run})
            if not self.a.dry_run:
                subprocess.run(shlex.split(cmd), check=True)
            self.nodes_restored = True

    def floor_step(self):
        """Fast path between governor decisions: add the nodes that pending and running pod requests need (nodepool mode)."""
        if self.killed() or self.a.mode != "nodepool" or not self.a.node_scale_cmd:
            return None
        s = snapshot(self.k, getattr(self.a, "active_nodes_only", False))
        n = max(1, s["nodes"]); per_node = s["alloc_m"] / n
        floor = max(int(math.ceil(s["req_m"] * (1.0 + self.a.headroom) / per_node)) if s["req_m"] > 0 else self.a.min_nodes, int(math.ceil(s["used_m"] / per_node)))
        floor = min(self.a.max_nodes, floor)
        if s["pending"] > 0 and floor > n and floor > (self.rec_n or 0):
            cmd = self.a.node_scale_cmd.format(n=floor)
            self.audit({"write": shlex.split(cmd), "why": "scheduling floor (pending pods)", "dry_run": self.a.dry_run})
            if not self.a.dry_run:
                subprocess.run(shlex.split(cmd), check=True)
            self.rec_n = floor
            return floor
        return None

    def step(self):
        if self.killed():
            self.restore()
            return self.audit({"decision": "killed", "mode": "observe"})
        s = snapshot(self.k, getattr(self.a, "active_nodes_only", False))
        n = max(1, s["nodes"]); per_node = s["alloc_m"] / n if n else 1.0
        if self.rec_n is None:
            self.rec_n = n
        repl = sum(int(h.get("status", {}).get("currentReplicas", 0) or 0) for h in s["hpas"]) or n
        power_stress = 0.0
        if self.a.power_cmd and self.a.site_limit_w:
            try:
                power_stress = float(subprocess.run(self.a.power_cmd, shell=True, capture_output=True, text=True).stdout.strip()) / self.a.site_limit_w
            except ValueError:
                power_stress = 0.0
        obs = {"queue_ratio": min(2.0, s["pending"] / max(1, repl)), "load_ratio": min(2.0, s["used_m"] / max(1.0, self.rec_n * per_node)),
               "power_stress": power_stress, "thermal": 0.0, "network_stress": 0.0, "drift_ratio": 0.0, "stale": 0.0, "security_block": 0.0}
        self.g.nodes = self.rec_n; self.g.current_cap = 1.0
        d = self.g.step(obs, 0)
        floor = max(int(math.ceil(s["req_m"] * (1.0 + self.a.headroom) / per_node)) if s["req_m"] > 0 else self.a.min_nodes, int(math.ceil(s["used_m"] / per_node)))
        rec_n = max(self.a.min_nodes, min(self.a.max_nodes, max(self.rec_n + int(d["node_delta"]), floor)))
        rho = max(0.5, min(0.95, float(d["demand"])))
        out = self.audit({"decision": {"nodes_observed": n, "nodes_recommended": rec_n, "hpa_target_recommended": round(rho, 3),
                                       "E": d["state"]["E"], "U": d["state"]["U"], "pending": s["pending"]}, "mode": self.a.mode})
        if self.a.mode in ("target", "nodepool"):
            want = int(round(rho * 100))
            for h in s["hpas"]:
                idx, cur = cpu_target(h)
                if cur is None or abs(cur - want) < self.a.min_target_change:
                    continue
                ns, name = h["metadata"]["namespace"], h["metadata"]["name"]
                self.changed.setdefault((ns, name), int(h["metadata"].get("annotations", {}).get(ANNOTATION, cur)))
                self.k.write(["annotate", "hpa", name, "-n", ns, "--overwrite", f"{ANNOTATION}={self.changed[(ns, name)]}"], "record original target")
                self.k.write(["patch", "hpa", name, "-n", ns, "--type=json", "-p",
                              json.dumps([{"op": "replace", "path": f"/spec/metrics/{idx}/resource/target/averageUtilization", "value": want}])],
                             f"HPA target to rho* = {want}%")
        if self.a.mode == "nodepool" and self.a.node_scale_cmd and rec_n != n:
            cfg = SimpleNamespace(minimum_nodes=self.a.min_nodes, maximum_nodes=self.a.max_nodes)
            acts, hits = enforce([{"action": "nodes", "target": rec_n, "direction": 1 if rec_n > n else -1}],
                                 {"actual_nodes": n, "power_cap": 1.0}, {"power_stress": power_stress, "security_block": 0.0}, cfg,
                                 ShieldLimits(power_limit=1e9, max_node_step=max(self.a.max_node_step, floor - n)))
            for act in acts:
                cmd = self.a.node_scale_cmd.format(n=int(act["target"]))
                self.audit({"write": shlex.split(cmd), "why": "node pool size", "dry_run": self.a.dry_run, "shield_interventions": hits})
                if not self.a.dry_run:
                    subprocess.run(shlex.split(cmd), check=True)
        self.rec_n = rec_n
        return out


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["observe", "target", "nodepool"], default="observe")
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between governor decisions")
    ap.add_argument("--floor-interval", type=float, default=15.0, help="seconds between scheduling-floor checks (nodepool mode)")
    ap.add_argument("--iterations", type=int, default=0, help="0 = run until stopped")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--kubectl", default="kubectl")
    ap.add_argument("--audit", default="omni_audit.jsonl")
    ap.add_argument("--kill-file", default="/tmp/omni.kill")
    ap.add_argument("--node-scale-cmd", default="")
    ap.add_argument("--min-nodes", type=int, default=1)
    ap.add_argument("--max-nodes", type=int, default=1000)
    ap.add_argument("--max-node-step", type=int, default=2)
    ap.add_argument("--min-target-change", type=int, default=3)
    ap.add_argument("--headroom", type=float, default=0.5, help="spare capacity kept above pod requests (0.5 = 50%%, the default)")
    ap.add_argument("--active-nodes-only", action="store_true",
                    help="count only schedulable nodes (not cordoned, not tainted NoSchedule) and the pods and usage on them")
    ap.add_argument("--node-restore-cmd", default="", help="command run once when the kill switch fires, returning the node pool to native")
    ap.add_argument("--power-cmd", default="")
    ap.add_argument("--site-limit-w", type=float, default=0.0)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    c = Controller(a); i = 0
    while a.iterations == 0 or i < a.iterations:
        c.step(); i += 1
        if a.iterations == 0 or i < a.iterations:
            waited = 0.0
            while waited + 1e-9 < a.interval:
                dt = min(a.floor_interval, a.interval - waited) if a.mode == "nodepool" else a.interval - waited
                time.sleep(dt); waited += dt
                if a.mode == "nodepool" and waited + 1e-9 < a.interval:
                    c.floor_step()


if __name__ == "__main__":
    main()
