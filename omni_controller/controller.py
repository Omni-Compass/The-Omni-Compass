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
from omni_controller.muscles import Muscles, add_args as add_muscle_args

ANNOTATION = "omnicompass.io/original-target-utilization"
RANGE_ANN = "omnicompass.io/original-replica-range"


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
        self.m = Muscles(self.k, a, self.audit)
        self.cl = None
        if getattr(a, "closure", ""):
            from omnicompass.closure import ClosureLaw, ClosureNodes
            law = json.load(open(a.closure))
            law = law.get("setting", law).get("closure", law)
            self.cl = ClosureNodes(ClosureLaw(**{k: v for k, v in law.items() if k != "site"}))
        self.lp_hist = []

    def audit(self, rec):
        rec = {"time": time.time(), **rec}
        if self.log:
            self.log.write(json.dumps(rec) + "\n"); self.log.flush()
        return rec

    def killed(self):
        return os.environ.get("OMNI_KILL") == "1" or (self.a.kill_file and Path(self.a.kill_file).exists())

    def restore(self):
        for h in self.k.get("get", "hpa", "-A", "-o", "json")["items"]:
            rng = h["metadata"].get("annotations", {}).get(RANGE_ANN)
            if rng:
                lo0, hi0 = (int(x) for x in rng.split(","))
                ns, name = h["metadata"]["namespace"], h["metadata"]["name"]
                self.k.write(["patch", "hpa", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"minReplicas": lo0, "maxReplicas": hi0}})],
                             "kill switch: restore the HPA's own replica range")
                self.k.write(["annotate", "hpa", name, "-n", ns, f"{RANGE_ANN}-"], "kill switch: remove range record")
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
        self.m.restore()
        cmd = getattr(self.a, "node_restore_cmd", "")
        if cmd and not self.nodes_restored:
            self.audit({"write": shlex.split(cmd), "why": "kill switch: restore node pool", "dry_run": self.a.dry_run})
            if not self.a.dry_run:
                subprocess.run(shlex.split(cmd), check=True)
            self.nodes_restored = True

    def strict_step(self, s, obs):
        """Strict C: Omni-Compass decides each deployment's replica count itself (the HPA no longer decides): replicas =
        ceil(current x measured utilisation / target utilisation), up at once, down only to the highest recommendation
        of the last --strict-window decisions; the HPA is pinned to that count (minReplicas = maxReplicas), within its
        original range; the kill switch restores the original range."""
        hist = getattr(self, "_rec_hist", {}); self._rec_hist = hist
        for h in s["hpas"]:
            ns, name = h["metadata"]["namespace"], h["metadata"]["name"]
            ann = h["metadata"].get("annotations", {}) or {}
            lo0, hi0 = (int(x) for x in ann.get(RANGE_ANN, f"{h['spec'].get('minReplicas', 1)},{h['spec']['maxReplicas']}").split(","))
            idx, tgt = cpu_target(h)
            orig_t = int(ann.get(ANNOTATION, tgt or 50))
            cur = int(h.get("status", {}).get("currentReplicas", 0) or lo0)
            util = None
            for m in h.get("status", {}).get("currentMetrics", []) or []:
                if m.get("type") == "Resource" and m.get("resource", {}).get("name") == "cpu":
                    util = m["resource"].get("current", {}).get("averageUtilization")
            if util is None:
                continue
            rec = max(lo0, min(hi0, int(math.ceil(cur * float(util) / orig_t - 1e-9))))
            hh = (hist.get((ns, name), []) + [rec])[-self.a.strict_window:]; hist[(ns, name)] = hh
            want = rec if rec >= cur else max(hh)
            if obs.get("security_block", 0.0) > 0.5:
                want = min(want, cur)                     # shield I1: no expansion during a security hold
            if RANGE_ANN not in ann:
                self.k.write(["annotate", "hpa", name, "-n", ns, "--overwrite", f"{RANGE_ANN}={lo0},{hi0}"], "strict: record original replica range")
            if h["spec"].get("minReplicas") != want or h["spec"]["maxReplicas"] != want:
                self.k.write(["patch", "hpa", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"minReplicas": want, "maxReplicas": want}})],
                             f"strict: replicas {cur} -> {want} decided by Omni-Compass (utilisation {util}%, target {orig_t}%)")

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
        extra = self.m.sense(power_stress)
        lp = extra.pop("latency_pressure", 0.0); p95 = extra.pop("latency_p95_ms", None)
        obs.update(extra)
        obs["queue_ratio"] = min(2.0, max(obs["queue_ratio"], lp))
        # SLO reflex: while the response-time target is breached, and for --slo-clear decisions after, Omni-Compass may
        # not pack replicas tighter than the workload's own HPA target and may not cap power (no energy at service's cost)
        self.lp_hist.append(lp)
        guarded = bool(getattr(self.a, "latency_file", "")) and getattr(self.a, "slo_ms", 0)
        n_clear = getattr(self.a, "slo_clear", 3)
        obs["slo_clean"] = (not guarded) or (len(self.lp_hist) >= n_clear and all(x == 0.0 for x in self.lp_hist[-n_clear:]))
        self.g.nodes = self.rec_n; self.g.current_cap = 1.0
        d = self.g.step(obs, 0)
        floor = max(int(math.ceil(s["req_m"] * (1.0 + self.a.headroom) / per_node)) if s["req_m"] > 0 else self.a.min_nodes, int(math.ceil(s["used_m"] / per_node)))
        rec_n = max(self.a.min_nodes, min(self.a.max_nodes, max(self.rec_n + int(d["node_delta"]), floor)))
        if self.cl is not None:
            # the benchmarked law drives the machines: the closure law on requested cores (omnicompass/closure.py), the
            # scheduling floor stays underneath it
            self.cl.observe(s["req_m"] / 1000.0)
            cl_n = self.cl.decide(n, per_node / 1000.0, self.g.last_push, self.a.min_nodes, self.a.max_nodes)
            rec_n = max(self.a.min_nodes, min(self.a.max_nodes, max(cl_n, floor)))
        rho = max(0.5, min(0.95, float(d["demand"])))
        from omnicompass.nervous_system import from_governor
        auth = from_governor(self.g, obs, d, mode="autopilot" if self.a.mode in ("target", "nodepool") else "observe")
        self.m.auth = auth
        if rec_n < n and not auth["organs"].get("nodes", {}).get("contract", False):
            rec_n = n            # nervous system: the node organ has no authority to give machines back now
        out = self.audit({"authority": {"calm": round(auth["scalars"]["calm"], 3), "execute": auth["execute"],
                                        "contract": {o: v.get("contract") for o, v in auth["organs"].items()}}})
        out = self.audit({"decision": {"nodes_observed": n, "nodes_recommended": rec_n, "law": "closure" if self.cl is not None else "governor", "hpa_target_recommended": round(rho, 3),
                                       "E": d["state"]["E"], "U": d["state"]["U"], "pending": s["pending"],
                                       "power_cap": round(float(d["power_cap"]), 3), "change_permitted": bool(d["change_permitted"]),
                                       "rollback_authorized": bool(d["rollback_authorized"]),
                                       "thermal": round(obs["thermal"], 3), "security_block": obs["security_block"],
                                       "power_stress": round(power_stress, 3), "latency_p95_ms": p95,
                                       "queue_ratio": round(obs["queue_ratio"], 3), "slo_clean": obs["slo_clean"]}, "mode": self.a.mode})
        if self.a.mode in ("target", "nodepool") and getattr(self.a, "strict_replicas", False):
            self.strict_step(s, obs)
            self.m.push(d, obs)
        elif self.a.mode in ("target", "nodepool"):
            want = int(round(rho * 100))
            for h in s["hpas"]:
                idx, cur = cpu_target(h)
                if cur is None:
                    continue
                ns, name = h["metadata"]["namespace"], h["metadata"]["name"]
                orig = int(h["metadata"].get("annotations", {}).get(ANNOTATION, cur))
                want_h = want if obs["slo_clean"] else min(want, orig)
                if abs(cur - want_h) < self.a.min_target_change and not (not obs["slo_clean"] and cur > orig):
                    continue
                if cur == want_h:
                    continue
                self.changed.setdefault((ns, name), int(h["metadata"].get("annotations", {}).get(ANNOTATION, cur)))
                self.k.write(["annotate", "hpa", name, "-n", ns, "--overwrite", f"{ANNOTATION}={self.changed[(ns, name)]}"], "record original target")
                self.k.write(["patch", "hpa", name, "-n", ns, "--type=json", "-p",
                              json.dumps([{"op": "replace", "path": f"/spec/metrics/{idx}/resource/target/averageUtilization", "value": want_h}])],
                             f"HPA target to rho* = {want_h}%" + ("" if obs["slo_clean"] else " (SLO reflex: not tighter than native)"))
            self.m.push(d, obs)
        if self.a.mode == "nodepool" and self.a.node_scale_cmd and rec_n != n:
            cfg = SimpleNamespace(minimum_nodes=self.a.min_nodes, maximum_nodes=self.a.max_nodes)
            acts, hits = enforce([{"action": "nodes", "target": rec_n, "direction": 1 if rec_n > n else -1}],
                                 {"actual_nodes": n, "power_cap": 1.0}, {"power_stress": power_stress, "security_block": obs["security_block"]}, cfg,
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
    ap.add_argument("--closure", default="", help="JSON with the closure-law setting (e.g. tuning/GLOBAL_LEAGUE_PREREGISTRATION.json): the benchmarked law decides the node count")
    ap.add_argument("--strict-replicas", action="store_true", help="strict C: Omni-Compass sets replica counts; the HPA is pinned")
    ap.add_argument("--strict-window", type=int, default=5, help="decisions a scale-down waits for (highest recent recommendation)")
    ap.add_argument("--max-failures", type=int, default=3, help="consecutive failed decisions before the fail-safe restore")
    ap.add_argument("--headroom", type=float, default=0.5, help="spare capacity kept above pod requests (0.5 = 50%%, the default)")
    ap.add_argument("--active-nodes-only", action="store_true",
                    help="count only schedulable nodes (not cordoned, not tainted NoSchedule) and the pods and usage on them")
    ap.add_argument("--node-restore-cmd", default="", help="command run once when the kill switch fires, returning the node pool to native")
    add_muscle_args(ap)
    ap.add_argument("--power-cmd", default="")
    ap.add_argument("--site-limit-w", type=float, default=0.0)
    return ap


def safe_step(c, fails):
    """One decision. A failed decision is recorded and skipped; after --max-failures in a row the controller hands the
    cluster back to native (kill-switch restore) and stops, so a dead controller never leaves its settings in place."""
    try:
        c.step()
        return 0
    except Exception as e:
        fails += 1
        err = getattr(e, "stderr", "") or ""
        c.audit({"error": repr(e)[:500], "stderr": str(err)[-500:], "consecutive_failures": fails})
        print(f"decision failed ({fails} in a row): {e!r} {err}", file=sys.stderr, flush=True)
        if fails >= c.a.max_failures:
            c.audit({"failsafe": "restoring native settings after repeated failures"})
            try:
                c.restore()
            finally:
                raise SystemExit(2)
        return fails


def main(argv=None):
    a = parser().parse_args(argv)
    c = Controller(a); i = 0; fails = 0
    while a.iterations == 0 or i < a.iterations:
        fails = safe_step(c, fails); i += 1
        if a.iterations == 0 or i < a.iterations:
            waited = 0.0
            while waited + 1e-9 < a.interval:
                dt = min(a.floor_interval, a.interval - waited) if a.mode == "nodepool" else a.interval - waited
                time.sleep(dt); waited += dt
                if a.mode == "nodepool" and waited + 1e-9 < a.interval:
                    try:
                        c.floor_step()
                    except Exception as e:
                        c.audit({"error": "floor check: " + repr(e)[:500], "stderr": str(getattr(e, "stderr", "") or "")[-500:]})


if __name__ == "__main__":
    main()
