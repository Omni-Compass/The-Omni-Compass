"""Omni-Compass live controller for a real Kubernetes cluster.

Modes
  observe   read the cluster every interval, run the fleet-mode governor in OBSERVE, log every decision; no writes (default)
  target    additionally patch each HPA's CPU averageUtilization to rho* (bounded, rate-limited); the Cluster Autoscaler and
            all node management remain unchanged
  nodepool  additionally size one node pool to the governor's recommendation through --node-scale-cmd, a command template
            such as "aws autoscaling set-desired-capacity --auto-scaling-group-name POOL --desired-capacity {n}"; the
            Cluster Autoscaler must not manage that pool
Laws (--law)
  governor  (default) the engine's allocation law sets the HPA target (rho*) and the closure law or the governor sizes the pool
  bowl      the bowl law (omnicompass/bowl.py) holds the service in its band, read as the GPU bowl reads it: the mean
            response time of the latency window between the bare service time (a tenth of --slo-ms) and --slo-ms, held at
            --bowl-center (0.4); p95 at or past the SLO, a blind sense or pods waiting for a place read as past the wall. Its push and pull move two levers: each HPA's CPU target inside its cover (from 60% of the
            operator's target up to the operator's own, never tighter than native, so it only ever adds pods and gives them
            back) and the node pool (one machine back only while the force is clearly down, the position below the center
            and the nervous system's release gate open; past the 0.95 wall, one machine up at once). The verdict
            (omnicompass/verdict.py, stepwise) decides how many machines may be given back at all: while the service is
            calm, one more machine is given back on trial and the response time of the requests served without it is set
            against the requests served just before and against the cluster as it ran on its own at the start; at most
            --allow slower and that machine stays given back, slower than that and it is taken back and not tried again
            for --verdict-recheck decisions. Where no machine passes, the pool stays as the cluster runs it alone. The
            six-state engine still runs every decision: it grants the authority, feeds the release gate and the compass,
            and is audited
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

import argparse, csv, json, math, os, shlex, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass import master
from omnicompass.adapter import Governor, mode_law, OBSERVE
from omnicompass.shield import enforce, ShieldLimits
from omni_controller.muscles import Muscles, add_args as add_muscle_args

ANNOTATION = "omnicompass.io/original-target-utilization"
BOWL_UP, BOWL_DOWN, BOWL_RELEASE = 0.10, 0.02, -0.2   # the bowl's gains, the same on every muscle (realms/bowl_arm.py)
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


IDLE_TAINT = "omnicompass.io/idle"   # PreferNoSchedule: new pods go elsewhere first, but land here at once if they must


def closed(n):
    """A machine I have closed to new work: marked idle (PreferNoSchedule) or cordoned."""
    spec = n.get("spec", {})
    return bool(spec.get("unschedulable")) or any(t.get("key") == IDLE_TAINT for t in spec.get("taints") or [])


def schedulable(n):
    """Open to new work: not closed by me, and not tainted NoSchedule (the control plane)."""
    spec = n.get("spec", {})
    return not closed(n) and not any(t.get("effect") == "NoSchedule" for t in spec.get("taints") or [])


def snapshot(k: Kube, active_only: bool = False):
    nodes = k.get("get", "nodes", "-o", "json")["items"]
    ready = [n for n in nodes if any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"].get("conditions", []))]
    pods = k.get("get", "pods", "-A", "-o", "json")["items"]
    if active_only:
        # in service: open to new work, or still carrying work (an idling worker keeps serving until its work is gone)
        carrying = {p["spec"].get("nodeName") for p in pods if p["status"].get("phase") in ("Running", "Pending")
                    and all(o.get("kind") != "DaemonSet" for o in p.get("metadata", {}).get("ownerReferences", []) or [])}
        ready = [n for n in ready if schedulable(n) or (closed(n) and n["metadata"]["name"] in carrying)]
    # open: the machines I keep open to new work. My machine orders are counted here; a machine I closed that still
    # carries work stays in service (in the energy count) until its work leaves on its own
    open_n = sum(1 for n in ready if schedulable(n))
    names = {n["metadata"]["name"] for n in ready}
    alloc = sum(to_milli(n["status"]["allocatable"]["cpu"]) for n in ready)
    req = sum(to_milli(c.get("resources", {}).get("requests", {}).get("cpu", "0")) for p in pods
              if p["status"].get("phase") in ("Running", "Pending")
              and (not active_only or p["status"].get("phase") == "Pending" or p["spec"].get("nodeName") in names)
              for c in p["spec"]["containers"])
    pending = sum(1 for p in pods if p["status"].get("phase") == "Pending")
    top = k.get("top", "nodes", "--no-headers")
    used = sum(to_milli(line.split()[1]) for line in top.strip().splitlines()
               if line.strip() and (not active_only or line.split()[0] in names))
    hpas = k.get("get", "hpa", "-A", "-o", "json")["items"]
    return {"nodes": len(ready), "open": open_n if active_only else len(ready), "alloc_m": alloc, "req_m": req, "used_m": used, "pending": pending, "hpas": hpas}


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
        # the machine organ's own engine view: fed with machine-attributable pressure only (pods waiting for a place)
        self.gn = Governor(law=mode_law("fleet")); self.gn.set_mode(OBSERVE)
        self.rec_n = None
        self.changed = {}
        self.target_at = {}            # (ns, hpa) -> when I last set its target
        self.nodes_restored = False
        self.m = Muscles(self.k, a, self.audit)
        self.cl = None
        if getattr(a, "closure", ""):
            from omnicompass.closure import ClosureLaw, ClosureNodes
            law = json.load(open(a.closure))
            law = law.get("setting", law).get("closure", law)
            law = {k: v for k, v in law.items() if k != "site"}
            # live decisions are 60 s apart, not simulator ticks: a rise the release band absorbs over the release horizon
            # does not veto a release (derived from the band itself, no new constant)
            from omnicompass.nervous_system import BAND
            law["rho_max"] = min(law.get("rho_max", 0.95), BAND[1])     # the living band: no machine filled past 95%
            law.setdefault("turn_rise", law.get("delta_rel", -1.0) if law.get("delta_rel", -1.0) >= 0 else law.get("delta", 0.05))
            self.cl = ClosureNodes(ClosureLaw(**law))
        self.lp_hist = []
        self.cmd_nodes = None          # efferent record: the node count last commanded (proprioception reads it back)
        self.cmd_hpa = {}              # efferent record: HPA targets last written
        from omnicompass.compass import Compass
        gp = self.g.p                  # the compass reads the engine in the engine's own parameters
        self.compass = Compass(E_max=gp.E_max, alpha_s=gp.alpha_s, beta_s=gp.beta_s, delta=gp.delta)
        self.s_floor = None            # bare service time (ms): the fastest a request is served with no queue ahead of it
        self.reflex = {}               # (ns, name) -> replica floor the pod reflex holds while the queue says it is needed
        self.pod_cap = {}              # (ns, name) -> request / limit share: what the HPA's target means in queue terms
        self.bowl = None
        if getattr(a, "law", "governor") == "bowl":
            from omnicompass.bowl import Band, Bowl
            # one decision every --interval s; the service follows a target in about one HPA sync plus a pod start (tau)
            self.bowl = Bowl(Band(0.0, 1.0, center=getattr(a, "bowl_center", 0.4)), dt=a.interval,
                             tau=getattr(a, "bowl_tau", 60.0), kp=1.0, smooth=0.3)
            self.bowl.kd *= 3.0                    # the same push as on every realm muscle (realms/bowl_arm.py)
            from omnicompass.verdict import Verdict
            self.verdict = Verdict(tolerance=getattr(a, "allow", 0.02), min_samples=getattr(a, "verdict_samples", 200),
                                   probe_every=getattr(a, "verdict_every", 10), recheck=getattr(a, "verdict_recheck", 120),
                                   max_trial=20, incremental=True)
        self.n_native = None           # the machines the cluster ran on its own when Omni started (the verdict's step 0)
        self.lat_t = None              # elapsed_seconds of the last request the verdict has seen
        self.bowl_x = {}               # (ns, name) -> the bowl's continuous HPA target, before rounding

    def _new_latencies(self):
        """Response times (ms) of the requests served since the last decision (the probe's latency file)."""
        lf = getattr(self.a, "latency_file", "")
        if not lf:
            return []
        try:
            rows = list(csv.DictReader(open(lf)))
        except OSError:
            return []
        out, last = [], self.lat_t
        for row in rows:
            t, ms = row.get("elapsed_seconds"), row.get("latency_ms")
            if row.get("ok") != "1" or not t or not ms:
                continue
            t = float(t)
            if last is None or t > last:
                out.append(float(ms))
                self.lat_t = t if self.lat_t is None else max(self.lat_t, t)
        return [] if last is None else out

    def audit(self, rec):
        rec = {"time": time.time(), **rec}
        if self.log:
            self.log.write(json.dumps(rec) + "\n"); self.log.flush()
        return rec

    def killed(self):
        # this controller's own switch, or the master switch for the whole harness (omnicompass/master.py)
        return (os.environ.get("OMNI_KILL") == "1" or (self.a.kill_file and Path(self.a.kill_file).exists())
                or master.is_off())

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

    def _gain(self, h):
        """The CPU each pod of the HPA's deployment is guaranteed, over the operator's limit (1 when nothing conveyed):
        g = min(mean conveyed limit, 0.95 A / ceil(maxReplicas / machines in service)) / L. The guaranteed share is the
        one each pod keeps with the autoscaler's largest count spread over the machines in service, so the target it
        sets moves only when a machine idles or wakes, never each time a pod starts or leaves."""
        from omnicompass.nervous_system import BAND
        ns = h["metadata"]["namespace"]; ref_ = h.get("spec", {}).get("scaleTargetRef", {}) or {}
        key = (ns, ref_.get("name", ""))
        g = self.m.gain.get(key, 1.0); base = self.m.base.get(key, 0.0); s = getattr(self, "_snap", None)
        if base > 0 and s and s.get("nodes"):
            ann = h["metadata"].get("annotations", {}) or {}
            hi0 = int(ann.get(RANGE_ANN, f"1,{h['spec'].get('maxReplicas', 1)}").split(",")[1])
            per_node = s["alloc_m"] / s["nodes"]
            g = min(g, BAND[1] * per_node / math.ceil(hi0 / s["nodes"]) / base)
        return max(1.0, g)

    def strict_step(self, s, obs):
        """Strict C: Omni-Compass decides each deployment's replica floor itself: replicas = ceil(current x measured
        utilisation / target utilisation), up at once, down only to the highest recommendation of the last
        --strict-window decisions; the HPA's minReplicas is set to that count, within its original range. Growth is never
        blocked: maxReplicas stays the operator's, so the HPA remains the fast up-reflex between Omni's decisions (the HPA
        reacts every 15 s; a count frozen for a 60 s decision would answer a load step up to 45 s late). The Unified
        Control Switch restores the original range."""
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
            rec = max(lo0, min(hi0, int(math.ceil(cur * float(util) / (orig_t * self._gain(h)) - 1e-9))))
            hh = (hist.get((ns, name), []) + [rec])[-self.a.strict_window:]; hist[(ns, name)] = hh
            want = rec if rec >= cur else max(hh)
            want = max(want, min(hi0, self.reflex.get((ns, name), 0)))   # the fast pod reflex's floor stands while held
            if obs.get("security_block", 0.0) > 0.5:
                want = min(want, cur)                     # shield I1: no expansion during a security hold
            if RANGE_ANN not in ann:
                self.k.write(["annotate", "hpa", name, "-n", ns, "--overwrite", f"{RANGE_ANN}={lo0},{hi0}"], "strict: record original replica range")
            if h["spec"].get("minReplicas") != want or h["spec"]["maxReplicas"] != hi0:
                self.k.write(["patch", "hpa", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"minReplicas": want, "maxReplicas": hi0}})],
                             f"strict: replica floor {cur} -> {want} decided by Omni-Compass (utilisation {util}%, target {orig_t}%); growth stays free up to {hi0}")

    def pod_reflex(self):
        """The fast pod reflex (manuscript Section 5.3, preemptive coherence): the HPA's own staffing rule,
        replicas = current x busy / target, read from the live queue instead of CPU averages a minute old.

        Busy comes from queueing physics: a replica serving requests in processor sharing answers in R = S / (1 - u),
        so u = 1 - S / R, with S the bare service time (the fastest tenth of the window's requests, those with no queue
        ahead) and R the mean response of the same window. The operator's target is a share of the pod's CPU request; the queue runs on
        its limit, so the same promise in queue terms is target x request / limit. The reflex only raises the replica
        floor to what that rule needs now and hands it back the moment the queue no longer needs it: no padding, no new
        target, the operator's own promise met sooner. Zero cluster reads while the queue is calm."""
        lf = getattr(self.a, "latency_file", "")
        if not lf or self.killed() or self.a.mode not in ("target", "nodepool"):
            return None
        from omni_controller.muscles import latency_window
        w = latency_window(lf, getattr(self.a, "reflex_window_s", 30.0))
        if w["blind"] or len(w["ms"]) < 5:
            return None
        p10 = sorted(w["ms"])[len(w["ms"]) // 10]
        # S and R from the same window: the fastest tenth of the requests answered now, at the CPU the pods have now. An
        # all-time fastest would read every later change of a pod's CPU limit (convey) as a queue that is not there
        self.s_floor = p10
        R = sum(w["ms"]) / len(w["ms"])
        u = max(0.0, min(0.99, 1.0 - self.s_floor / R)) if R > 0 else 0.0
        if u <= 0.0 and not self.reflex:
            return None                          # calm and nothing held: no read, no write
        out = {}
        for h in self.k.get("get", "hpa", "-A", "-o", "json")["items"]:
            idx, tgt = cpu_target(h)
            if tgt is None:
                continue
            ns, name = h["metadata"]["namespace"], h["metadata"]["name"]
            ann = h["metadata"].get("annotations", {}) or {}
            lo0, hi0 = (int(x) for x in ann.get(RANGE_ANN, f"{h['spec'].get('minReplicas', 1)},{h['spec']['maxReplicas']}").split(","))
            orig_t = int(ann.get(ANNOTATION, tgt)) / 100.0
            key = (ns, name)
            if key not in self.pod_cap:
                ref = h["spec"]["scaleTargetRef"]
                c0 = self.k.get("get", ref["kind"].lower(), ref["name"], "-n", ns, "-o", "json")["spec"]["template"]["spec"]["containers"][0]
                req = to_milli(c0.get("resources", {}).get("requests", {}).get("cpu", "0") or "0")
                lim = to_milli(c0.get("resources", {}).get("limits", {}).get("cpu", "0") or "0")
                self.pod_cap[key] = (req / lim) if req > 0 and lim > 0 else 1.0
            u_star = max(0.05, orig_t * self.pod_cap[key])       # the operator's promise in queue terms
            cur = int(h.get("status", {}).get("currentReplicas", 0) or lo0)
            desired = int(h.get("status", {}).get("desiredReplicas", 0) or cur)
            need = min(hi0, int(math.ceil(cur * u / u_star - 1e-9)))
            held = self.reflex.get(key)
            if not getattr(self.a, "pod_reflex_writes", False):
                # the autoscaler is the muscle that makes and removes pods; I gauge what the queue needs and write
                # nothing, so no pod is started or stopped that the muscle itself would not start or stop
                if need > max(cur, desired):
                    self.audit({"pod_reflex_reading": {f"{ns}/{name}": need}, "replicas": cur, "busy": round(u, 3),
                                "promise": round(u_star, 3), "R_ms": round(R, 1), "S_ms": round(self.s_floor, 1)})
                continue
            if need > max(cur, desired, h["spec"].get("minReplicas", 1) or 1):
                if RANGE_ANN not in ann:
                    self.k.write(["annotate", "hpa", name, "-n", ns, "--overwrite", f"{RANGE_ANN}={lo0},{hi0}"], "pod reflex: record original replica range")
                self.k.write(["patch", "hpa", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"minReplicas": need}})],
                             f"pod reflex: floor {need} (queue busy {u:.2f} vs promise {u_star:.2f}, R {R:.0f} ms, S {self.s_floor:.0f} ms)")
                self.reflex[key] = need; out[key] = need
            elif held is not None and need <= max(desired, lo0):
                # the queue no longer needs the floor (or the HPA has caught up): hand it back. On top, the operator's
                # own minimum returns; in strict C the floor is Omni's own replica decision again (strict_step)
                del self.reflex[key]; out[key] = None
                if not getattr(self.a, "strict_replicas", False) and h["spec"].get("minReplicas") == held:
                    self.k.write(["patch", "hpa", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"minReplicas": lo0}})],
                                 f"pod reflex: release floor {held} -> {lo0} (queue busy {u:.2f})")
                    out[key] = lo0
        if out:
            self.audit({"pod_reflex": {f"{k[0]}/{k[1]}": v for k, v in out.items()}, "busy": round(u, 3), "R_ms": round(R, 1), "S_ms": round(self.s_floor, 1)})
        return out

    def floor_step(self):
        """Fast path between governor decisions: add the nodes that pending and running pod requests need (nodepool mode)."""
        if self.killed() or self.a.mode != "nodepool" or not self.a.node_scale_cmd:
            return None
        self.pod_reflex()
        # energy to where the work is: a new serving pod gets its machine's idle CPU within three checks, not a decision
        self.ticks = getattr(self, "ticks", 0) + 1
        if getattr(self.a, "latency_file", "") and self.ticks % 3 == 0:
            try:
                self.m.convey()
            except Exception as e:  # a failed conveyance writes nothing more; the next one comes on time
                self.audit({"error": f"convey: {e}"})
        # one light read every check; the full snapshot (nodes, all pods, node metrics, HPAs) only when a pod waits. The
        # controller shares CPUs with the service it protects (on kind, one 4-core runner), so its reads cost latency
        if not str(self.k.get("get", "pods", "-A", "--field-selector=status.phase=Pending", "-o", "name")).strip():
            return None
        s = snapshot(self.k, getattr(self.a, "active_nodes_only", False))
        n = max(1, s["open"]); per_node = s["alloc_m"] / max(1, s["nodes"])
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
        s = snapshot(self.k, getattr(self.a, "active_nodes_only", False)); self._snap = s
        # my orders are judged by the machines open to work; a machine's capacity by the machines in service
        n = max(1, s["open"]); per_node = s["alloc_m"] / max(1, s["nodes"])
        if self.rec_n is None:
            self.rec_n = n
        repl = sum(int(h.get("status", {}).get("currentReplicas", 0) or 0) for h in s["hpas"]) or n
        power_stress = 0.0; blind = {}
        if self.a.power_cmd and self.a.site_limit_w:
            try:
                power_stress = float(subprocess.run(self.a.power_cmd, shell=True, capture_output=True, text=True).stdout.strip()) / self.a.site_limit_w
                blind["power"] = False
            except ValueError:
                power_stress = 0.0; blind["power"] = True
        # proprioception (efferent -> afferent): did the last commands land? drift = |observed - commanded| / commanded
        drift = {}
        if self.cmd_nodes is not None:
            drift["nodes"] = abs(n - self.cmd_nodes) / max(1, self.cmd_nodes)
        for h in s["hpas"]:
            key = (h["metadata"]["namespace"], h["metadata"]["name"])
            if key in self.cmd_hpa:
                _, cur_t = cpu_target(h)
                if cur_t is not None:
                    drift["hpa " + "/".join(key)] = abs(cur_t - self.cmd_hpa[key]) / max(1, self.cmd_hpa[key])
        nodes_landed = drift.get("nodes", 0.0) == 0.0
        self.cmd_nodes = None; self.cmd_hpa = {}
        obs = {"queue_ratio": min(2.0, s["pending"] / max(1, repl)), "load_ratio": min(2.0, s["used_m"] / max(1.0, self.rec_n * per_node)),
               "power_stress": power_stress, "thermal": 0.0, "network_stress": 0.0, "drift_ratio": max(drift.values(), default=0.0),
               "stale": 0.0, "security_block": 0.0}
        extra = self.m.sense(power_stress)
        lp = extra.pop("latency_pressure", 0.0); p95 = extra.pop("latency_p95_ms", None)
        if getattr(self.a, "latency_file", "") and getattr(self.a, "slo_ms", 0):
            blind["latency"] = bool(extra.pop("latency_blind", 0.0))
        age = extra.pop("latency_age_s", None)
        obs.update(extra)
        # afferent integrity: the share of declared senses that are blind enters the engine as its stale channel
        obs["stale"] = (sum(blind.values()) / len(blind)) if blind else 0.0
        obs["queue_ratio"] = min(2.0, max(obs["queue_ratio"], lp))
        # SLO reflex: while the response-time target is breached, and for --slo-clear decisions after, Omni-Compass may
        # not pack replicas tighter than the workload's own HPA target and may not cap power (no energy at service's cost)
        self.lp_hist.append(lp)
        guarded = bool(getattr(self.a, "latency_file", "")) and getattr(self.a, "slo_ms", 0)
        n_clear = getattr(self.a, "slo_clear", 3)
        obs["slo_clean"] = (not guarded) or (not blind.get("latency", False) and len(self.lp_hist) >= n_clear
                                             and all(x == 0.0 for x in self.lp_hist[-n_clear:]))
        self.g.nodes = self.rec_n; self.g.current_cap = 1.0
        d = self.g.step(obs, 0)
        floor = max(int(math.ceil(s["req_m"] * (1.0 + self.a.headroom) / per_node)) if s["req_m"] > 0 else self.a.min_nodes, int(math.ceil(s["used_m"] / per_node)))
        rec_n = max(self.a.min_nodes, min(self.a.max_nodes, max(self.rec_n + int(d["node_delta"]), floor)))
        rho = max(0.5, min(0.95, float(d["demand"])))
        from omnicompass.nervous_system import from_governor, node_release_gate
        mode = "autopilot" if self.a.mode in ("target", "nodepool") else "observe"
        auth = from_governor(self.g, obs, d, mode=mode)
        self.m.auth = auth
        breach_now = lp > 0.0 or blind.get("latency", False)
        # the machine organ's view: only pressure a machine release could cause (pods waiting for a place, a live
        # breach). Power and heat are relieved by a release, never worsened by it, so they cannot veto one
        obs_n = dict(obs, queue_ratio=min(2.0, s["pending"] / max(1, repl)), slo_clean=not breach_now,
                     power_stress=0.0, thermal=0.0)
        self.gn.nodes = self.rec_n; self.gn.current_cap = 1.0
        dn = self.gn.step(obs_n, 0)
        auth_n = from_governor(self.gn, obs_n, dn, mode=mode)
        if self.cl is not None:
            # the benchmarked law drives the machines: the closure law on requested cores (omnicompass/closure.py), the
            # scheduling floor stays underneath it
            self.cl.observe(s["req_m"] / 1000.0)
            # the machine organ's own pressure (as its release gate): pods waiting and live breaches, not modelled heat
            # or the whole body's latency push, which a machine release does not cause
            cl_n = self.cl.decide(n, per_node / 1000.0, self.gn.last_push, self.a.min_nodes, self.a.max_nodes)
            rec_n = max(self.a.min_nodes, min(self.a.max_nodes, max(cl_n, floor)))
        bowl_rec = None
        if self.bowl is not None:
            # the service position in its bowl, read as the GPU bowl reads it (omni_controller/gpu_bowl.py): the mean
            # response time of the window between the bare service time (a tenth of the SLO) and the SLO; p95 at or
            # past the SLO, a blind sense, or a pod waiting for a place is past the wall
            slo = float(getattr(self.a, "slo_ms", 0) or 0)
            pos = 0.0
            if slo > 0 and getattr(self.a, "latency_file", ""):
                from omni_controller.muscles import latency_window
                w = latency_window(self.a.latency_file, getattr(self.a, "latency_window_s", 60.0))["ms"]
                bare = slo / 10.0
                mean = sum(w) / len(w) if w else (p95 or 0.0)
                pos = max(0.0, (mean - bare) / (slo - bare))
            if blind.get("latency", False) or s["pending"] > 0 or (p95 is not None and slo > 0 and p95 >= slo):
                pos = 1.0
            F = self.bowl.force(pos)
            # the verdict: the response times of the requests served since the last decision, at the machines the pool
            # stood at; then how many machines may be given back at all (or the count a trial needs)
            if self.n_native is None:
                self.n_native = n
            self.verdict.observe(self._new_latencies())
            calm = self.bowl.p < self.bowl.band.wall_high and s["pending"] == 0 and not breach_now
            deepest, trial, ev = self.verdict.tick(calm)
            if ev:
                self.audit({"verdict": ev, "state": self.verdict.state, "machines_given_back_allowed": self.verdict.allowed,
                            "machines_native": self.n_native})
            if self.bowl.p >= self.bowl.band.wall_high:
                rec_n = max(floor, n + 1)                                  # fail up: one machine more at once
            elif trial:
                rec_n = max(floor, self.n_native - deepest)                # the trial's count (one machine per decision below)
            elif F < BOWL_RELEASE and self.bowl.p < self.bowl.band.center and self.n_native - (n - 1) <= deepest:
                rec_n = max(floor, n - 1)                                  # one back, if the verdict and the release gate agree
            else:
                rec_n = max(floor, n)
            rec_n = max(self.a.min_nodes, min(self.a.max_nodes, rec_n))
            bowl_rec = {"position": round(self.bowl.p, 4), "velocity": round(self.bowl.v, 4), "force": round(F, 4),
                        "verdict_state": self.verdict.state, "machines_given_back_allowed": self.verdict.allowed}
        scaling_up = any(int(h.get("status", {}).get("desiredReplicas", 0) or 0) > int(h.get("status", {}).get("currentReplicas", 0) or 0)
                         for h in s["hpas"])
        gate = node_release_gate(n, per_node, s["used_m"], s["pending"], scaling_up, breach_now, rho, auth_n,
                                 senses_live=not any(blind.values()), last_command_landed=nodes_landed)
        if rec_n < n and not gate["ok"]:
            rec_n = n            # nervous system: the machine organ may not give a machine back now (reason audited)
        elif rec_n < n:
            rec_n = n - 1        # one machine per decision: release is the slow, reversible direction
        out = self.audit({"authority": {"calm": round(auth["scalars"]["calm"], 3), "execute": auth["execute"],
                                        "contract": {o: v.get("contract") for o, v in auth["organs"].items()},
                                        "scalars": {k: round(v, 3) for k, v in auth["scalars"].items()},
                                        "node_view": {"calm": round(auth_n["scalars"]["calm"], 3),
                                                      "scalars": {k: round(v, 3) for k, v in auth_n["scalars"].items()}},
                                        "node_gate": {"ok": gate["ok"], "reason": gate["reason"], "util_after": round(gate["util_after"], 3)},
                                        "senses": {"blind": blind, "latency_age_s": None if age is None else round(age, 1), "stale": obs["stale"]},
                                        "proprioception": {k: round(v, 3) for k, v in drift.items()}}})
        # the compass: where the engine stands on the wheel, whether every level is inside Omega, whether the move at a
        # boundary points inward, and the ledger step
        fill = s["req_m"] / max(1.0, s["alloc_m"])
        levels = {"machine_fill": fill}
        moves = {"machine_fill": (1.0 if rec_n < n else -1.0 if rec_n > n else 0.0)}
        for o in ("cpufreq", "gpu", "power"):
            env = auth["organs"].get(o, {}).get("envelope")
            if env:
                levels[f"{o}_ceiling"] = env[1]
        forced = obs["queue_ratio"] > 0.0 or s["pending"] > 0
        self.audit({"compass": self.compass.read(d["state"]["E"], d["state"]["S"], levels, moves, forced, x=self.g.x, p=self.g.p)})
        out = self.audit({"decision": {"nodes_observed": n, "nodes_recommended": rec_n,
                                       "law": "bowl" if self.bowl is not None else "closure" if self.cl is not None else "governor",
                                       "bowl": bowl_rec, "hpa_target_recommended": round(rho, 3),
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
            for h in s["hpas"]:
                idx, cur = cpu_target(h)
                if cur is None:
                    continue
                ns, name = h["metadata"]["namespace"], h["metadata"]["name"]
                orig = int(h["metadata"].get("annotations", {}).get(ANNOTATION, cur))
                # more headroom is always allowed; less never: at a given load fewer pods always means a longer M/M/c wait
                # (no target above the operator's keeps the wait), so a raise only spends latency.
                # Omni on top earns its keep on machines, not by packing the operator's pods tighter
                # the same promise in queue terms: busy = target x request / limit. While convey() gives the pods a
                # limit g times the operator's, the target that keeps each pod exactly as busy is g times higher
                want = int(round(100 * min(rho, orig / 100.0) * self._gain(h)))
                if self.bowl is not None:
                    # the bowl's push and pull on the target, inside its cover [60% of the operator's, the operator's]
                    # (in queue terms, times the conveyed gain): a lower target is more pods, so the up force lowers it
                    g_ = self._gain(h); hi_t = orig * g_; lo_t = max(10.0, 0.6 * orig) * g_
                    x = self.bowl_x.get((ns, name), hi_t)
                    if self.bowl.p >= self.bowl.band.wall_high:
                        x = lo_t                                         # fail up: the most pods the cover allows, at once
                    else:
                        F_ = bowl_rec["force"]
                        x = x - (BOWL_UP if F_ > 0 else BOWL_DOWN) * F_ * (hi_t - lo_t)
                    x = max(lo_t, min(hi_t, x)); self.bowl_x[(ns, name)] = x
                    want = int(round(x))
                want_h = want if obs["slo_clean"] else min(want, orig)
                if abs(cur - want_h) < self.a.min_target_change and not (not obs["slo_clean"] and cur > orig):
                    continue
                if cur == want_h:
                    continue
                # the muscle's own clock: the autoscaler takes its scale-down window (300 s unless the operator set one)
                # to answer a target. A new target inside that window moves the muscle mid-movement and starts pods it
                # then removes, so I hold each target for one window. A response-time breach returns the operator's
                # target at once
                win = float(((h["spec"].get("behavior") or {}).get("scaleDown") or {}).get("stabilizationWindowSeconds", 300))
                last = self.target_at.get((ns, name))
                if obs["slo_clean"] and last is not None and time.time() - last < win:
                    continue
                self.target_at[(ns, name)] = time.time()
                self.changed.setdefault((ns, name), int(h["metadata"].get("annotations", {}).get(ANNOTATION, cur)))
                self.k.write(["annotate", "hpa", name, "-n", ns, "--overwrite", f"{ANNOTATION}={self.changed[(ns, name)]}"], "record original target")
                self.k.write(["patch", "hpa", name, "-n", ns, "--type=json", "-p",
                              json.dumps([{"op": "replace", "path": f"/spec/metrics/{idx}/resource/target/averageUtilization", "value": want_h}])],
                             f"HPA target to rho* = {want_h}%" + ("" if obs["slo_clean"] else " (SLO reflex: not tighter than native)"))
                self.cmd_hpa[(ns, name)] = want_h
            self.m.push(d, obs)
        if self.a.mode in ("target", "nodepool"):
            self.pod_reflex()
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
                    self.cmd_nodes = int(act["target"])
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
    ap.add_argument("--law", choices=["governor", "bowl"], default="governor",
                    help="governor (default): the engine's allocation law; bowl: the bowl law on the HPA target and the node pool")
    ap.add_argument("--allow", type=float, default=0.02, help="the most a machine given back may add to the response time")
    ap.add_argument("--verdict-samples", type=int, default=200, help="requests measured before and after a machine is given back on trial")
    ap.add_argument("--verdict-every", type=int, default=10, help="decisions between trials")
    ap.add_argument("--verdict-recheck", type=int, default=120, help="decisions before a refused machine is tried again")
    ap.add_argument("--bowl-tau", type=float, default=60.0, help="seconds the service takes to follow a lever (the bowl's damping)")
    ap.add_argument("--bowl-center", type=float, default=0.4,
                    help="where the bowl holds the service (0 the bare service time, 1 the SLO); 0.4, as the GPU governor")
    ap.add_argument("--closure", default="", help="JSON with the closure-law setting (e.g. tuning/GLOBAL_LEAGUE_PREREGISTRATION.json): the benchmarked law decides the node count")
    ap.add_argument("--strict-replicas", action="store_true", help="strict C: Omni-Compass sets replica counts; the HPA is pinned")
    ap.add_argument("--pod-reflex-writes", action="store_true",
                    help="let the pod reflex raise the HPA's replica floor itself (default: it gauges and writes nothing)")
    ap.add_argument("--reflex-window-s", type=float, default=30.0, help="window of probe samples the fast pod reflex reads")
    ap.add_argument("--strict-window", type=int, default=5, help="decisions a scale-down waits for (highest recent recommendation)")
    ap.add_argument("--headroom", type=float, default=0.5, help="spare capacity kept above pod requests (0.5 = 50%%, the default)")
    ap.add_argument("--active-nodes-only", action="store_true",
                    help="count only nodes in service (schedulable, or cordoned but still carrying work) and the pods and usage on them")
    ap.add_argument("--node-restore-cmd", default="", help="command run once when the kill switch fires, returning the node pool to native")
    add_muscle_args(ap)
    ap.add_argument("--power-cmd", default="")
    ap.add_argument("--site-limit-w", type=float, default=0.0)
    return ap


def safe_step(c, fails):
    """One decision. A failed decision is recorded and skipped: it writes nothing, so the cluster keeps the last settings
    that landed, and the next decision comes at the normal cadence. There is no automated fallback (manuscript Section
    5.8: the Unified Control Switch is mechanical, explicit, operator-controlled and 'does not rely on automated fallback
    inference'). Only a human flips the switch, for the whole harness at once: --kill-file present (or OMNI_KILL=1) turns
    Omni-Compass OFF and hands every setting back to native; removing it turns Omni-Compass back ON. Boundaries are never
    handled by switching anything off: the living band and the shield clamp every level inside its range."""
    try:
        c.step()
        return 0
    except Exception as e:
        fails += 1
        err = getattr(e, "stderr", "") or ""
        c.audit({"error": repr(e)[:500], "stderr": str(err)[-500:], "consecutive_failures": fails})
        print(f"decision failed ({fails} in a row): {e!r} {err}", file=sys.stderr, flush=True)
        return fails


def main(argv=None):
    a = parser().parse_args(argv)
    master.refuse_if_off("kubernetes controller")
    c = Controller(a); i = 0; fails = 0
    master.register("kubernetes controller")
    import signal

    def master_off(*_):
        # the master switch pulled from the command line (tools/omni_switch.py off): hand everything back now and exit
        try:
            c.restore()
        finally:
            c.audit({"decision": "master switch: OFF; every setting handed back; exiting"})
            sys.exit(0)
    signal.signal(signal.SIGTERM, master_off)
    import atexit, resource
    t0 = time.time()
    def overhead():   # the controller's own cost: CPU seconds of this process and every kubectl/script it ran
        me, kids = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime
        c.audit({"overhead": {"cpu_s": round(cpu, 2), "wall_s": round(time.time() - t0, 1),
                              "cores_mean": round(cpu / max(1e-9, time.time() - t0), 4)}})
    atexit.register(overhead)
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
