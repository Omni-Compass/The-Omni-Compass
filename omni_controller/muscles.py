"""Live muscles for the Kubernetes controller beyond HPA and nodes.

Each muscle pulls (afferent) and pushes (efferent) through kubectl, records what it changed so the kill switch can hand
the muscle back, and tags every write with its muscle name in the audit log.

  power_cap   push: CPU limit of each running pod of the capped deployments = base limit x the governor's power cap,
              resized in place (no restart; Linux CFS quota throttles the containers for real); pull: power from --power-cmd
  heat        pull: thermal state from the harness heat law driven by live power stress (modelled: kind has no thermometer)
  security    pull: ConfigMap key "hold" == "true" means a security hold; the shield then blocks every expansion
  rollout     push: pause a deployment's rollout while the governor does not permit change; resume it when it does;
              undo a rollout that has exceeded its progress deadline when the governor authorises rollback
  batch       push: admit (unsuspend) held batch Jobs, one per decision, only when change is permitted and there is load
              and power headroom; running Jobs are never suspended
  latency     pull: 95th-percentile response time over the last --latency-window-s from --latency-file (CSV written by
              scripts/latency_probe.py); pressure max(0, p95 / --slo-ms - 1) enters the engine as queue pressure
  cpu_pstate  hardware connector. pull: --rapl-cmd prints package watts (e.g. from /sys/class/powercap/intel-rapl);
              push: --cpufreq-cmd with {khz}, the frequency ceiling = max frequency x power cap (e.g. writing
              scaling_max_freq with scripts/cpufreq_ceiling.sh {khz}, see hardware/SCHEDUTIL.md, or `cpupower frequency-set -u {khz}kHz`); kill runs it with the maximum frequency
  gpu         hardware connector. pull: --gpu-query-cmd prints "watts,celsius" (e.g. `nvidia-smi
              --query-gpu=power.draw,temperature.gpu --format=csv,noheader,nounits`); GPU temperature / --gpu-temp-limit
              feeds the heat sense; push: --gpu-power-cmd with {w}, the power limit = max limit x power cap
              (e.g. `nvidia-smi -pl {w}`); kill restores the maximum limit
  rightsize   push: each running pod's CPU *request* follows its measured use x (1 + headroom), resized in place through the
              pods/resize subresource (no restart); never above the limit, never below --rightsize-min-m; no decrease while
              the SLO is breached, no increase during a security hold; kill restores every original request
  coldstart   push: a deployment with no work waiting (ConfigMap key "queue" == 0, the queue a KEDA scaler would read) for
              --coldstart-idle decisions is scaled to zero; it is scaled back to its recorded replica count the moment
              work is waiting; kill restores the recorded count
  batch_pace  push: while power stress or heat is high, one running Job labelled omnicompass.io/pausable=true is suspended
              per decision (checkpointed training pauses instead of the site going over its limit); it is resumed when
              stress and heat are back down; kill resumes every Job Omni paused
  contain     push: an agent namespace whose measured CPU use exceeds --contain-cpu-m, or any namespace during a security
              hold, gets a ResourceQuota (limits.cpu = budget) and its running pods' CPU limits are scaled in place so the
              total fits the budget; lifted when use is back under budget; kill deletes the quota and restores the limits
  cooling     facility connector. push: --cooling-cmd with {c}, the supply-air setpoint moved between --cooling-min-c and
              --cooling-max-c by the heat state (warm setpoint while cool, saving chiller energy; cold setpoint as heat
              rises); kill runs it with --cooling-restore-c
  Hardware connectors are off unless their commands are given (not available on CI runners); the mechanism is the same.
"""
from __future__ import annotations

import csv, json, math, shlex, subprocess, time
import re

CPU_ANN = "omnicompass.io/original-cpu-limit"
PAUSE_ANN = "omnicompass.io/paused-by-omni"
BATCH_LABEL = "omnicompass.io/batch=true"
PAUSABLE_LABEL = "omnicompass.io/pausable=true"
REQ_ANN = "omnicompass.io/original-cpu-request"
REPL_ANN = "omnicompass.io/original-replicas"
PACE_ANN = "omnicompass.io/paced-by-omni"
QUOTA = "omni-containment"
LIM_ANN = "omnicompass.io/original-limits"


def milli(v):
    v = str(v)
    return float(v[:-1]) if v.endswith("m") else float(v) * 1000.0


def ref(s):
    ns, name = s.split("/", 1)
    return ns, name


class Muscles:
    def __init__(self, k, a, audit):
        self.k, self.a, self.audit = k, a, audit
        self.gain = {}       # (ns, deployment) -> mean conveyed CPU limit / operator's limit
        self.base = {}       # (ns, deployment) -> operator's CPU limit (millicores)
        self.thermal = 0.32  # harness initial thermal state

    # ---- afferent ---------------------------------------------------------------------------------------------------
    def sense(self, power_stress):
        o = {}
        if getattr(self.a, "thermal_model", False):
            self.thermal = min(1.35, max(0.0, 0.86 * self.thermal + 0.14 * (0.34 + 0.62 * min(1.35, power_stress))))
            o["thermal"] = self.thermal
        if getattr(self.a, "rapl_cmd", ""):
            o["cpu_watts"] = self._read(self.a.rapl_cmd)
        if getattr(self.a, "gpu_query_cmd", ""):
            out = self._run_out(self.a.gpu_query_cmd)
            try:
                w, t = [float(x) for x in out.split(",")[:2]]
                o["gpu_watts"], o["gpu_celsius"] = w, t
                o["thermal"] = max(o.get("thermal", 0.0), min(1.35, t / max(1.0, self.a.gpu_temp_limit)))
            except ValueError:
                pass
        lf = getattr(self.a, "latency_file", "")
        if lf and getattr(self.a, "slo_ms", 0):
            ls = latency_sense(lf, self.a.latency_window_s)
            o["latency_blind"] = 1.0 if ls["blind"] else 0.0
            o["latency_age_s"] = ls["age_s"]
            if not ls["blind"]:
                o["latency_p95_ms"] = ls["p95"]
                o["latency_pressure"] = max(0.0, ls["p95"] / self.a.slo_ms - 1.0)
                if ls["fail"]:        # failed requests in a live window are real service failures: full pressure share
                    o["latency_pressure"] = max(o["latency_pressure"], ls["fail"] / (ls["ok"] + ls["fail"]))
        cm = getattr(self.a, "security_configmap", "")
        if cm:
            ns, name = ref(cm)
            try:
                data = self.k.get("get", "configmap", name, "-n", ns, "-o", "json").get("data", {}) or {}
                o["security_block"] = 1.0 if str(data.get("hold", "")).lower() == "true" else 0.0
            except Exception:
                o["security_block"] = 0.0
        return o

    def _run_out(self, cmd):
        return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()

    def _read(self, cmd):
        try:
            return float(self._run_out(cmd).split()[0])
        except (ValueError, IndexError):
            return float("nan")

    def _hw(self, template, value, why):
        cmd = template.format(khz=int(value), w=int(value), v=value)
        self.audit({"write": shlex.split(cmd), "why": why, "dry_run": self.a.dry_run})
        if not self.a.dry_run:
            subprocess.run(shlex.split(cmd), check=True)

    # ---- efferent ---------------------------------------------------------------------------------------------------
    def push(self, d, obs, killed=False):
        if killed:
            return
        self._power_cap(float(d["power_cap"]), obs)
        self._hardware(float(d["power_cap"]), obs)
        self._rollout(bool(d["change_permitted"]), bool(d["rollback_authorized"]))
        self._batch(bool(d["change_permitted"]), obs)
        for name, fn in (("rightsize", lambda: self._rightsize(obs)), ("coldstart", self._coldstart),
                         ("batch_pace", lambda: self._batch_pace(obs)), ("contain", lambda: self._contain(obs)),
                         ("cooling", lambda: self._cooling(obs))):
            self._guard(name, fn)

    def _may(self, organ, what):
        """Nervous-system authority for an organ ("expand", "contract", "admit", "pause"); without it, everything allowed."""
        a = getattr(self, "auth", None)
        if not a:
            return True
        return bool(a.get("organs", {}).get(organ, {}).get(what, False))

    def _envelope(self, organ, default):
        a = getattr(self, "auth", None)
        return (a or {}).get("organs", {}).get(organ, {}).get("envelope", default)

    def _guard(self, name, fn):
        """One lever failing is logged and never stops the others (nor the kill switch)."""
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            err = getattr(e, "stderr", "") or str(e)
            self.audit({"error": f"{name}: {type(e).__name__}: {str(err).strip()[:400]}"})

    # ---- new levers ---------------------------------------------------------------------------------------------------
    def _named_usage(self, ns, sel=None):
        args = ["top", "pods", "-n", ns, "--no-headers"] + (["-l", sel] if sel else [])
        try:
            out = self.k.get(*args)
        except Exception:
            return {}
        return {line.split()[0]: milli(line.split()[1]) for line in str(out).strip().splitlines() if line.strip()}

    def _rightsize(self, obs):
        for target in filter(None, getattr(self.a, "rightsize_deployments", "").split(",")):
            ns, name = ref(target)
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            ann = dep["metadata"].get("annotations", {}) or {}
            c0 = dep["spec"]["template"]["spec"]["containers"][0].get("resources", {})
            base = c0.get("requests", {}).get("cpu")
            if base is None:
                continue
            if REQ_ANN not in ann:
                self.k.write(["annotate", "deployment", name, "-n", ns, f"{REQ_ANN}={int(milli(base))}m"], "rightsize: record original CPU request")
            sel = ",".join(f"{k}={v}" for k, v in dep["spec"]["selector"]["matchLabels"].items())
            use = self._named_usage(ns, sel)
            for pod in self._pods(dep, ns):
                pn = pod["metadata"]["name"]
                if pn not in use:
                    continue
                res = pod["spec"]["containers"][0].get("resources", {})
                cur = milli(res.get("requests", {}).get("cpu", base))
                lim = milli(res.get("limits", {}).get("cpu", "1000000m"))
                want = int(min(lim, max(self.a.rightsize_min_m, math.ceil(use[pn] * (1.0 + self.a.rightsize_headroom) / 10.0) * 10)))
                if want < cur and (not obs.get("slo_clean", True) or not self._may("pods", "contract")):
                    continue  # SLO reflex / nervous system: no shrinking without contraction authority
                if want > cur and obs.get("security_block", 0.0) > 0.5:
                    continue  # shield I1: no expansion during a security hold
                if abs(want - cur) < self.a.cap_min_change_m:
                    continue
                self.k.write(["patch", "pod", pn, "-n", ns, "--subresource", "resize", "--type=json", "-p",
                              json.dumps([{"op": "replace", "path": "/spec/containers/0/resources/requests/cpu", "value": f"{want}m"}])],
                             f"rightsize: CPU request {int(cur)}m -> {want}m in place (use {int(use[pn])}m)")

    def _coldstart(self):
        sig = getattr(self.a, "coldstart_signal", "")
        if not sig:
            return
        sns, sname = ref(sig)
        try:
            q = float((self.k.get("get", "configmap", sname, "-n", sns, "-o", "json").get("data") or {}).get("queue", "0"))
        except Exception:
            return
        self._idle = getattr(self, "_idle", 0) + 1 if q <= 0 else 0
        for target in filter(None, getattr(self.a, "coldstart_deployments", "").split(",")):
            ns, name = ref(target)
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            ann = dep["metadata"].get("annotations", {}) or {}
            rep = int(dep["spec"].get("replicas", 1))
            if q > 0 and rep == 0 and REPL_ANN in ann:
                self.k.write(["scale", "deployment", name, "-n", ns, f"--replicas={ann[REPL_ANN]}"], f"coldstart: wake to {ann[REPL_ANN]} (queue {q:g})")
            elif self._idle >= self.a.coldstart_idle and rep > 0 and self._may("pods", "contract"):
                self.k.write(["annotate", "deployment", name, "-n", ns, "--overwrite", f"{REPL_ANN}={rep}"], "coldstart: record replicas")
                self.k.write(["scale", "deployment", name, "-n", ns, "--replicas=0"], f"coldstart: scale to zero (idle {self._idle} decisions)")

    def _batch_pace(self, obs):
        if not getattr(self.a, "batch_pace", False):
            return
        hot = obs.get("power_stress", 0.0) >= self.a.pace_high or obs.get("thermal", 0.0) >= self.a.pace_heat \
            or (getattr(self, "auth", None) is not None and self._may("batch", "pause"))
        calm = obs.get("power_stress", 1.0) <= self.a.pace_low and obs.get("thermal", 1.0) < self.a.pace_heat - 0.06
        jobs = self.k.get("get", "jobs", "-A", "-l", PAUSABLE_LABEL, "-o", "json")["items"]
        if hot:
            run = [j for j in jobs if not j["spec"].get("suspend")]
            if run:
                j = run[0]; ns, name = j["metadata"]["namespace"], j["metadata"]["name"]
                self.k.write(["annotate", "job", name, "-n", ns, "--overwrite", f"{PACE_ANN}=true"], "batch_pace: record pause")
                self.k.write(["patch", "job", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"suspend": True}})],
                             f"batch_pace: pause job (power stress {obs.get('power_stress', 0.0):.2f}, heat {obs.get('thermal', 0.0):.2f})")
        elif calm:
            paced = [j for j in jobs if j["spec"].get("suspend") and (j["metadata"].get("annotations") or {}).get(PACE_ANN) == "true"]
            if paced:
                self._resume_job(paced[0], "batch_pace: resume job (stress and heat back down)")

    def _resume_job(self, j, why):
        ns, name = j["metadata"]["namespace"], j["metadata"]["name"]
        self.k.write(["patch", "job", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"suspend": False}})], why)
        self.k.write(["annotate", "job", name, "-n", ns, f"{PACE_ANN}-"], "batch_pace: clear pause record")

    def _quota(self, ns):
        try:
            return self.k.get("get", "resourcequota", QUOTA, "-n", ns, "-o", "json")
        except Exception:
            return None

    def _contain(self, obs):
        """Contain on over-budget use or a security hold; while contained each running pod gets an equal share of the
        budget as its CPU limit (in place); lift only when use is under 80% of the budget (release band) and no hold."""
        for ns in filter(None, getattr(self.a, "contain_namespaces", "").split(",")):
            total = sum(self._named_usage(ns).values())
            budget = float(self.a.contain_cpu_m)
            hold = obs.get("security_block", 0.0) > 0.5
            q = self._quota(ns)
            if q is None and (total > budget or hold):
                self.k.write(["create", "quota", QUOTA, "-n", ns, f"--hard=limits.cpu={int(budget)}m"],
                             f"contain: quota limits.cpu={int(budget)}m (use {int(total)}m)")
                q = {"metadata": {"annotations": {}}}
            elif q is not None and total < 0.8 * budget and not hold:
                self._release(ns, q, "contain: use back under budget, lift containment")
                continue
            if q is None:
                continue
            held = json.loads((q["metadata"].get("annotations") or {}).get(LIM_ANN, "{}"))
            run = [p for p in self.k.get("get", "pods", "-n", ns, "-o", "json")["items"] if p["status"].get("phase") == "Running"
                   and p["spec"]["containers"][0].get("resources", {}).get("limits", {}).get("cpu") is not None]
            share = max(10, int(budget / max(1, len(run)) / 10) * 10)
            changed = False
            for p in run:
                pn = p["metadata"]["name"]; lim = p["spec"]["containers"][0]["resources"]["limits"]["cpu"]
                if pn not in held:
                    held[pn] = lim; changed = True
                want = min(share, int(milli(held[pn])))
                if int(milli(lim)) != want:
                    self.k.write(["patch", "pod", pn, "-n", ns, "--subresource", "resize", "--type=json", "-p",
                                  json.dumps([{"op": "replace", "path": "/spec/containers/0/resources/limits/cpu", "value": f"{want}m"}])],
                                 f"contain: pod CPU limit {lim} -> {want}m in place (budget share)")
            if changed:
                # the original limits live on the quota object, so a kill switch in any process can restore them
                self.k.write(["annotate", "resourcequota", QUOTA, "-n", ns, "--overwrite", f"{LIM_ANN}={json.dumps(held, sort_keys=True)}"],
                             "contain: record original pod CPU limits")

    def _release(self, ns, q, why):
        # the quota goes first: while it stands, Kubernetes refuses to raise a pod's limit back above the budget share
        held = json.loads((q["metadata"].get("annotations") or {}).get(LIM_ANN, "{}"))
        self.k.write(["delete", "resourcequota", QUOTA, "-n", ns], f"{why}: delete quota")
        for pn, lim in held.items():
            self._guard(f"{why} {pn}", lambda pn=pn, lim=lim: self.k.write(
                ["patch", "pod", pn, "-n", ns, "--subresource", "resize", "--type=json", "-p",
                 json.dumps([{"op": "replace", "path": "/spec/containers/0/resources/limits/cpu", "value": lim}])],
                f"{why}: restore pod CPU limit {lim}"))

    def _cooling(self, obs):
        cmd = getattr(self.a, "cooling_cmd", "")
        if not cmd:
            return
        th = obs.get("thermal", 0.5)
        x = min(1.0, max(0.0, (th - 0.5) / 0.5))
        c = round(self.a.cooling_max_c - (self.a.cooling_max_c - self.a.cooling_min_c) * x, 1)
        c = round(min(c, max(self.a.cooling_min_c, self._envelope("cooling", [0, 99])[1])), 1)   # nervous-system envelope
        if abs(c - getattr(self, "_setpoint", -99.0)) >= 0.5:
            self._hw(cmd.replace("{c}", "{v}"), c, f"cooling: supply-air setpoint {c} C (heat {th:.2f})")
            self._setpoint = c

    def _pods(self, dep, ns):
        sel = ",".join(f"{k}={v}" for k, v in dep["spec"]["selector"]["matchLabels"].items())
        return [p for p in self.k.get("get", "pods", "-n", ns, "-l", sel, "-o", "json")["items"]
                if p["status"].get("phase") == "Running"]

    def _pod_usage(self, dep, ns):
        sel = ",".join(f"{k}={v}" for k, v in dep["spec"]["selector"]["matchLabels"].items())
        try:
            out = self.k.get("top", "pods", "-n", ns, "-l", sel, "--no-headers")
        except Exception:
            return []
        return [milli(line.split()[1]) for line in str(out).strip().splitlines() if line.strip()]

    def _resize(self, pod, ns, value, why):
        self.k.write(["patch", "pod", pod["metadata"]["name"], "-n", ns, "--subresource", "resize", "--type=json", "-p",
                      json.dumps([{"op": "replace", "path": "/spec/containers/0/resources/limits/cpu", "value": value}])], why)

    def _power_cap(self, cap, obs):
        """In-place pod resize (no restart): each running pod's CPU limit = base limit x cap; the kernel's CFS quota
        enforces it. The deployment template is not changed, so no rollout is triggered."""
        if not obs.get("slo_clean", True):
            cap = 1.0  # SLO reflex: no power capping while service is (or was just) over its response-time target
        if getattr(self.a, "latency_file", ""):
            # a request-served workload: its work is set by arrivals, not by the cap, so throttling it saves no energy
            # (the same CPU-seconds run later) and only adds wait. The energy goes where the work is: convey()
            return self.convey(obs)
        for target in filter(None, getattr(self.a, "cap_deployments", "").split(",")):
            ns, name = ref(target)
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            ann = dep["metadata"].get("annotations", {}) or {}
            c0 = dep["spec"]["template"]["spec"]["containers"][0]
            tmpl = c0.get("resources", {}).get("limits", {}).get("cpu")
            if tmpl is None:
                continue
            base = milli(ann.get(CPU_ANN, tmpl))
            req = milli(c0.get("resources", {}).get("requests", {}).get("cpu", "0"))
            want = int(max(req, round(base * max(self.a.cap_min, min(1.0, cap)) / 10.0) * 10))
            # reflex: never cap a pod below what it is using plus headroom (as the node muscle never goes below requests)
            use = self._pod_usage(dep, ns)
            if use:
                want = int(min(base, max(want, math.ceil(max(use) * (1.0 + self.a.cap_headroom) / 10.0) * 10)))
            if CPU_ANN not in ann:
                self.k.write(["annotate", "deployment", name, "-n", ns, f"{CPU_ANN}={int(base)}m"], "power_cap: record original CPU limit")
            for pod in self._pods(dep, ns):
                cur = milli(pod["spec"]["containers"][0].get("resources", {}).get("limits", {}).get("cpu", tmpl))
                if obs.get("security_block", 0.0) > 0.5 and want > cur:
                    continue  # shield I1: no expansion during a security hold
                if abs(want - cur) < self.a.cap_min_change_m:
                    continue
                self._resize(pod, ns, f"{want}m", f"power_cap: pod CPU limit to {want}m in place (cap {cap:.3f})")

    def convey(self, obs=None):
        """Energy to where the work is (omnicompass/conveyance.py, on one machine's CPU).

        A serving pod's CPU limit is a quota: a request that needs more CPU than one quota period allows waits for the
        next period, while the machine it runs on sits idle. That wait is energy withheld from the work, not saved: the
        request uses the same CPU-seconds either way. So each machine's idle CPU is conveyed to the serving pods on it:

            c_i = min( max(L_i, (0.95 A_j - Q_j) / |P_j|), 0.95 A_j )

        A_j the machine's allocatable CPU, Q_j the requests of every other pod on it, P_j the serving pods on it, L_i the
        operator's own limit. The machine's last five percent is never handed out (the living band), a pod never gets
        less than its operator gave it, and the requests (what the scheduler and the autoscaler read) are untouched.
        Resized in place through pods/resize: no pod restarts. No expansion during a security hold. The kill switch
        returns every pod to L_i.

        Only when needed (--convey-on, a share of --slo-ms): conveyance engages when the 95th-percentile response time
        reaches convey-on x SLO and disengages below convey-off x SLO, returning every serving pod to L_i. Between
        bursts the pods run at the operator's own limit, so the machine's spare CPU is not burned for speed nobody
        asked for. A blind latency sense engages it (service first). --convey-on 0 conveys always."""
        from omnicompass.nervous_system import BAND
        obs = obs or {}
        targets = [ref(t) for t in filter(None, getattr(self.a, "cap_deployments", "").split(","))]
        if not targets:
            return None
        engaged = self._convey_engaged()
        alloc = {n["metadata"]["name"]: milli(n["status"]["allocatable"]["cpu"])
                 for n in self.k.get("get", "nodes", "-o", "json")["items"]}
        pods = [p for p in self.k.get("get", "pods", "-A", "-o", "json")["items"]
                if p["status"].get("phase") in ("Running", "Pending") and p["spec"].get("nodeName")]
        out = {}
        for ns, name in targets:
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            ann = dep["metadata"].get("annotations", {}) or {}
            c0 = dep["spec"]["template"]["spec"]["containers"][0]
            tmpl = c0.get("resources", {}).get("limits", {}).get("cpu")
            if tmpl is None:
                continue
            base = milli(ann.get(CPU_ANN, tmpl))
            sel = dep["spec"]["selector"]["matchLabels"]
            mine = lambda p: p["metadata"].get("namespace", "default") == ns and all(
                (p["metadata"].get("labels", {}) or {}).get(k) == v for k, v in sel.items())
            serving, other = {}, {}
            for p in pods:
                node = p["spec"]["nodeName"]
                if mine(p) and p["status"].get("phase") == "Running":
                    serving.setdefault(node, []).append(p)
                elif not mine(p):
                    other[node] = other.get(node, 0.0) + sum(
                        milli(c.get("resources", {}).get("requests", {}).get("cpu", "0") or "0") for c in p["spec"]["containers"])
            if CPU_ANN not in ann and serving:
                self.k.write(["annotate", "deployment", name, "-n", ns, f"{CPU_ANN}={int(base)}m"], "convey: record original CPU limit")
            got = []
            for node, ps in serving.items():
                a_j = alloc.get(node, 0.0)
                share = (BAND[1] * a_j - other.get(node, 0.0)) / len(ps)
                want = int(min(max(base, math.floor(share / 10.0) * 10), BAND[1] * a_j)) if engaged else int(base)
                for p in ps:
                    cur = milli(p["spec"]["containers"][0].get("resources", {}).get("limits", {}).get("cpu", tmpl))
                    if obs.get("security_block", 0.0) > 0.5 and want > cur:
                        got.append(cur); continue  # shield I1: no expansion during a security hold
                    if abs(want - cur) < self.a.cap_min_change_m:
                        got.append(cur); continue
                    self._resize(p, ns, f"{want}m", f"convey: {node} idle CPU to its {len(ps)} serving pod(s), limit {want}m in place"
                                 if engaged else f"convey: response time calm, operator's limit {want}m in place")
                    out[f"{ns}/{p['metadata']['name']}"] = want; got.append(want)
            # the gain g = mean conveyed limit / operator's limit: the replica organ reads it to keep the operator's
            # promise in queue terms (target x request / limit) while the limit is larger
            self.gain[(ns, name)] = (sum(got) / len(got) / base) if got and base > 0 else 1.0
            self.base[(ns, name)] = base
        return out

    def _convey_engaged(self):
        """Hysteresis on the response time: on at convey-on x SLO, off below convey-off x SLO; blind engages."""
        on, off = getattr(self.a, "convey_on", 0.0), getattr(self.a, "convey_off", 0.0)
        lf, slo = getattr(self.a, "latency_file", ""), getattr(self.a, "slo_ms", 0.0)
        if not on or not lf or not slo:
            return True
        ls = latency_sense(lf, self.a.latency_window_s)
        was = getattr(self, "_conveying", False)
        now = True if ls["blind"] else (ls["p95"] >= on * slo or (was and ls["p95"] >= off * slo))
        if now != was:
            self.audit({"convey": "engaged" if now else "released", "p95_ms": None if ls["blind"] else round(ls["p95"], 1),
                        "slo_ms": slo, "blind": ls["blind"]})
        self._conveying = now
        return now

    def _hardware(self, cap, obs):
        cap = 1.0 if not obs.get("slo_clean", True) else max(self.a.cap_min, min(1.0, cap))
        if obs.get("security_block", 0.0) > 0.5:
            cap = min(cap, getattr(self, "_last_cap", 1.0))  # shield I1: no expansion during a security hold
        if abs(cap - getattr(self, "_last_cap", 1.0)) < 0.02:
            return
        if getattr(self.a, "cpufreq_policy_root", ""):
            self._cpufreq_sysfs(cap, obs)
        if getattr(self.a, "cpufreq_cmd", "") and self.a.cpu_max_khz:
            lo, hi = self._envelope("cpufreq", [0.0, 1.0]); cap = min(max(cap, lo), hi)
            self._hw(self.a.cpufreq_cmd, self.a.cpu_max_khz * cap, f"cpu_pstate: frequency ceiling {int(self.a.cpu_max_khz * cap)} kHz (cap {cap:.3f})")
        if getattr(self.a, "gpu_power_cmd", "") and self.a.gpu_max_w:
            self._hw(self.a.gpu_power_cmd, self.a.gpu_max_w * cap, f"gpu: power limit {int(self.a.gpu_max_w * cap)} W (cap {cap:.3f})")
        self._last_cap = cap

    def _cpufreq_sysfs(self, cap, obs):
        """CPU frequency ceiling through the kernel's own policy files (hardware/cpufreq.py).
        ceiling = min(max(cap, envelope floor, schedutil request), envelope ceiling), where the schedutil request is
        min(1, 1.25 u) at the current CPU utilisation u: the ceiling never cuts below the frequency schedutil itself
        would ask for, so it only removes headroom the scheduler is not using. The envelope ceiling (heat) wins last.
        The first write snapshots every policy; the kill switch restores those exact values."""
        from hardware.cpufreq import CpuFreqPolicies, schedutil_frequency_invariant
        if getattr(self, "_cf", None) is None:
            self._cf = CpuFreqPolicies(self.a.cpufreq_policy_root)
            snap = self._cf.capture_original()
            if getattr(self.a, "cpufreq_require_schedutil", False):
                self._cf.assert_schedutil()
            self.audit({"cpu_pstate_snapshot": [r.as_dict() for r in snap]})
        lo, hi = self._envelope("cpufreq", [0.0, 1.0])
        u = float(obs.get("cpu_util", obs.get("load_ratio", 1.0)))
        c = min(max(cap, lo, schedutil_frequency_invariant(u)), hi)
        w = self._cf.apply_cap(c, dry_run=self.a.dry_run)
        self.audit({"cpu_pstate_write": w, "why": f"cpu_pstate: ceiling {c:.3f} (cap {cap:.3f}, envelope [{lo:.3f}, {hi:.3f}], "
                                                  f"schedutil request {schedutil_frequency_invariant(u):.3f} at u {u:.3f})"})

    def _rollout(self, permitted, rollback):
        for target in filter(None, getattr(self.a, "rollout_guard", "").split(",")):
            ns, name = ref(target)
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            ann = dep["metadata"].get("annotations", {}) or {}
            paused = bool(dep["spec"].get("paused"))
            conds = {c["type"]: c for c in dep.get("status", {}).get("conditions", [])}
            stuck = conds.get("Progressing", {}).get("reason") == "ProgressDeadlineExceeded"
            if rollback and stuck:
                self.k.write(["rollout", "undo", f"deployment/{name}", "-n", ns], "rollout: undo stuck rollout (rollback authorised)")
                continue
            if not permitted and not paused:
                self.k.write(["annotate", "deployment", name, "-n", ns, "--overwrite", f"{PAUSE_ANN}=true"], "rollout: record pause")
                self.k.write(["rollout", "pause", f"deployment/{name}", "-n", ns], "rollout: pause (change not permitted)")
            elif permitted and paused and ann.get(PAUSE_ANN) == "true":
                self.k.write(["rollout", "resume", f"deployment/{name}", "-n", ns], "rollout: resume (change permitted)")
                self.k.write(["annotate", "deployment", name, "-n", ns, f"{PAUSE_ANN}-"], "rollout: clear pause record")

    def _batch(self, permitted, obs):
        if not getattr(self.a, "batch", False):
            return
        if not permitted or obs.get("security_block", 0.0) > 0.5:
            return
        if obs.get("load_ratio", 1.0) >= self.a.batch_load_max or obs.get("power_stress", 1.0) >= self.a.batch_power_max:
            return
        if not self._may("batch", "admit"):
            return
        jobs = self.k.get("get", "jobs", "-A", "-l", BATCH_LABEL, "-o", "json")["items"]
        held = sorted((j for j in jobs if j["spec"].get("suspend")), key=lambda j: j["metadata"].get("creationTimestamp", ""))
        if held:
            j = held[0]; ns, name = j["metadata"]["namespace"], j["metadata"]["name"]
            self.k.write(["patch", "job", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"suspend": False}})],
                         "batch: admit held job (headroom)")

    # ---- kill -------------------------------------------------------------------------------------------------------
    def restore(self):
        self._guard("kill cooling", self._restore_cooling)
        self._guard("kill contain", self._restore_contain)
        self._guard("kill batch_pace", self._restore_pace)
        self._guard("kill coldstart", self._restore_coldstart)
        self._guard("kill rightsize", self._restore_rightsize)
        self._guard("kill hardware and power cap", self._restore_core)

    def _restore_cooling(self):
        if getattr(self.a, "cooling_cmd", ""):
            self._hw(self.a.cooling_cmd.replace("{c}", "{v}"), self.a.cooling_restore_c, "kill switch: restore cooling setpoint")
            self._setpoint = None

    def _restore_contain(self):
        for ns in filter(None, getattr(self.a, "contain_namespaces", "").split(",")):
            q = self._quota(ns)
            if q is not None:
                self._release(ns, q, "kill switch")

    def _restore_pace(self):
        if getattr(self.a, "batch_pace", False):
            for j in self.k.get("get", "jobs", "-A", "-l", PAUSABLE_LABEL, "-o", "json")["items"]:
                if j["spec"].get("suspend") and (j["metadata"].get("annotations") or {}).get(PACE_ANN) == "true":
                    self._resume_job(j, "kill switch: resume paced job")

    def _restore_coldstart(self):
        for target in filter(None, getattr(self.a, "coldstart_deployments", "").split(",")):
            ns, name = ref(target)
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            ann = dep["metadata"].get("annotations", {}) or {}
            if REPL_ANN in ann:
                if int(dep["spec"].get("replicas", 1)) == 0:
                    self.k.write(["scale", "deployment", name, "-n", ns, f"--replicas={ann[REPL_ANN]}"], "kill switch: restore replicas")
                self.k.write(["annotate", "deployment", name, "-n", ns, f"{REPL_ANN}-"], "kill switch: clear replica record")

    def _restore_rightsize(self):
        for target in filter(None, getattr(self.a, "rightsize_deployments", "").split(",")):
            ns, name = ref(target)
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            orig = (dep["metadata"].get("annotations", {}) or {}).get(REQ_ANN)
            if orig:
                for pod in self._pods(dep, ns):
                    if pod["spec"]["containers"][0].get("resources", {}).get("requests", {}).get("cpu") != orig:
                        self.k.write(["patch", "pod", pod["metadata"]["name"], "-n", ns, "--subresource", "resize", "--type=json", "-p",
                                      json.dumps([{"op": "replace", "path": "/spec/containers/0/resources/requests/cpu", "value": orig}])],
                                     "kill switch: restore original CPU request in place")
                self.k.write(["annotate", "deployment", name, "-n", ns, f"{REQ_ANN}-"], "kill switch: remove request record")

    def _restore_core(self):
        if getattr(self, "_cf", None) is not None:
            self.audit({"cpu_pstate_restore": self._cf.restore(dry_run=self.a.dry_run), "why": "kill switch: exact pre-Omni CPU ceilings"})
        if getattr(self.a, "cpufreq_cmd", "") and self.a.cpu_max_khz and getattr(self, "_last_cap", 1.0) != 1.0:
            self._hw(self.a.cpufreq_cmd, self.a.cpu_max_khz, "kill switch: restore maximum CPU frequency")
        if getattr(self.a, "gpu_power_cmd", "") and self.a.gpu_max_w and getattr(self, "_last_cap", 1.0) != 1.0:
            self._hw(self.a.gpu_power_cmd, self.a.gpu_max_w, "kill switch: restore maximum GPU power limit")
        self._last_cap = 1.0
        for target in filter(None, getattr(self.a, "cap_deployments", "").split(",")):
            ns, name = ref(target)
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            orig = (dep["metadata"].get("annotations", {}) or {}).get(CPU_ANN)
            if orig:
                for pod in self._pods(dep, ns):
                    if pod["spec"]["containers"][0].get("resources", {}).get("limits", {}).get("cpu") != orig:
                        self._resize(pod, ns, orig, "kill switch: restore original pod CPU limit in place")
                self.k.write(["annotate", "deployment", name, "-n", ns, f"{CPU_ANN}-"], "kill switch: remove CPU record")
        for target in filter(None, getattr(self.a, "rollout_guard", "").split(",")):
            ns, name = ref(target)
            dep = self.k.get("get", "deployment", name, "-n", ns, "-o", "json")
            if (dep["metadata"].get("annotations", {}) or {}).get(PAUSE_ANN) == "true":
                self.k.write(["rollout", "resume", f"deployment/{name}", "-n", ns], "kill switch: resume rollout")
                self.k.write(["annotate", "deployment", name, "-n", ns, f"{PAUSE_ANN}-"], "kill switch: clear pause record")


def latency_sense(path, window_s, now=None):
    """The latency afferent with its integrity (manuscript Appendix J: the nervous system owns delay and dropout
    handling). Returns p95 of successful requests in the last window, the ok and failed counts in it, and the age of
    the newest sample against the wall clock. The sense is blind when its newest sample is older than two windows, or
    when the window holds no successful request: a hung probe stops writing, and its last clean window must not be read
    as the present."""
    import os, time
    try:
        age = (now if now is not None else time.time()) - os.path.getmtime(path)
        rows = list(csv.DictReader(open(path)))
    except OSError:
        return {"p95": float("nan"), "ok": 0, "fail": 0, "age_s": float("inf"), "blind": True}
    if not rows:
        return {"p95": float("nan"), "ok": 0, "fail": 0, "age_s": age, "blind": True}
    t_end = float(rows[-1]["elapsed_seconds"])
    win = [r for r in rows if float(r["elapsed_seconds"]) >= t_end - window_s]
    ms = sorted(float(r["latency_ms"]) for r in win if r.get("ok") == "1")
    fails = sum(1 for r in win if r.get("ok") != "1")
    p95 = ms[min(len(ms) - 1, int(0.95 * len(ms)))] if ms else float("nan")
    return {"p95": p95, "ok": len(ms), "fail": fails, "age_s": age, "blind": age > 2.0 * window_s or not ms}


def latency_window(path, window_s, now=None):
    """The last window_s seconds of successful probe samples (ms), with the same integrity rule as latency_sense."""
    import os, time
    try:
        age = (now if now is not None else time.time()) - os.path.getmtime(path)
        rows = list(csv.DictReader(open(path)))
    except OSError:
        return {"ms": [], "blind": True}
    if not rows:
        return {"ms": [], "blind": True}
    t_end = float(rows[-1]["elapsed_seconds"])
    ms = [float(r["latency_ms"]) for r in rows if r.get("ok") == "1" and float(r["elapsed_seconds"]) >= t_end - window_s]
    return {"ms": ms, "blind": age > 2.0 * window_s or not ms}


def latency_p95(path, window_s):
    """95th-percentile response time (ms) of successful requests in the last window_s seconds of the probe CSV."""
    try:
        rows = list(csv.DictReader(open(path)))
    except OSError:
        return float("nan")
    if not rows:
        return float("nan")
    t_end = float(rows[-1]["elapsed_seconds"])
    ms = sorted(float(r["latency_ms"]) for r in rows if r.get("ok") == "1" and float(r["elapsed_seconds"]) >= t_end - window_s)
    fails = sum(1 for r in rows if r.get("ok") != "1" and float(r["elapsed_seconds"]) >= t_end - window_s)
    if fails and not ms:
        return 1e9
    return ms[min(len(ms) - 1, int(0.95 * len(ms)))] if ms else float("nan")


def add_args(ap):
    ap.add_argument("--cap-deployments", default="", help="ns/name[,ns/name]: power_cap muscle scales their CPU limit")
    ap.add_argument("--cap-min", type=float, default=0.65, help="lowest power cap applied (shield floor)")
    ap.add_argument("--cap-min-change-m", type=int, default=20, help="smallest CPU-limit change written, millicores")
    ap.add_argument("--cap-headroom", type=float, default=0.3, help="power cap never below pod CPU usage x (1 + headroom)")
    ap.add_argument("--latency-file", default="", help="probe CSV (elapsed_seconds,latency_ms,ok) for the latency afferent")
    ap.add_argument("--slo-ms", type=float, default=0.0, help="95th-percentile response-time target, ms")
    ap.add_argument("--latency-window-s", type=float, default=60.0)
    ap.add_argument("--convey-on", type=float, default=0.5, help="convey idle CPU once p95 reaches this share of --slo-ms (0: always)")
    ap.add_argument("--convey-off", type=float, default=0.25, help="return pods to the operator's limit once p95 is below this share")
    ap.add_argument("--slo-clear", type=int, default=3, help="decisions the SLO must stay met before densifying or capping again")
    ap.add_argument("--thermal-model", action="store_true", help="heat muscle: thermal state from the harness heat law")
    ap.add_argument("--security-configmap", default="", help="ns/name of a ConfigMap whose key 'hold' signals a security hold")
    ap.add_argument("--rollout-guard", default="", help="ns/name[,ns/name]: rollout muscle pauses, resumes, undoes")
    ap.add_argument("--batch", action="store_true", help="batch muscle: admit held Jobs labelled " + BATCH_LABEL)
    ap.add_argument("--batch-load-max", type=float, default=0.8)
    ap.add_argument("--batch-power-max", type=float, default=0.9)
    ap.add_argument("--rapl-cmd", default="", help="cpu_pstate pull: prints CPU package watts")
    ap.add_argument("--cpufreq-cmd", default="", help="cpu_pstate push: command template with {khz}")
    ap.add_argument("--cpufreq-policy-root", default="", help="cpu_pstate push through sysfs policies (e.g. /sys/devices/system/cpu/cpufreq); exact restore on kill")
    ap.add_argument("--cpufreq-require-schedutil", action="store_true", help="refuse to act unless every policy runs schedutil")
    ap.add_argument("--cpu-max-khz", type=float, default=0.0)
    ap.add_argument("--gpu-query-cmd", default="", help="gpu pull: prints 'watts,celsius'")
    ap.add_argument("--gpu-power-cmd", default="", help="gpu push: command template with {w}")
    ap.add_argument("--gpu-max-w", type=float, default=0.0)
    ap.add_argument("--gpu-temp-limit", type=float, default=83.0, help="GPU temperature treated as thermal 1.0")
    ap.add_argument("--rightsize-deployments", default="", help="ns/name[,ns/name]: rightsize muscle sets pod CPU requests from use")
    ap.add_argument("--rightsize-headroom", type=float, default=0.3)
    ap.add_argument("--rightsize-min-m", type=int, default=50)
    ap.add_argument("--coldstart-deployments", default="", help="ns/name[,ns/name]: scaled to zero when idle, woken on work")
    ap.add_argument("--coldstart-signal", default="", help="ns/name of a ConfigMap whose key 'queue' is the waiting work")
    ap.add_argument("--coldstart-idle", type=int, default=3, help="idle decisions before scaling to zero")
    ap.add_argument("--batch-pace", action="store_true", help="batch_pace muscle: pause Jobs labelled " + PAUSABLE_LABEL + " under stress")
    ap.add_argument("--pace-high", type=float, default=0.95, help="power stress that pauses a job")
    ap.add_argument("--pace-low", type=float, default=0.8, help="power stress under which a paused job resumes")
    ap.add_argument("--pace-heat", type=float, default=0.96, help="heat state that pauses a job")
    ap.add_argument("--contain-namespaces", default="", help="ns[,ns]: agent namespaces held to --contain-cpu-m")
    ap.add_argument("--contain-cpu-m", type=float, default=1000.0)
    ap.add_argument("--cooling-cmd", default="", help="cooling push: command template with {c} (supply-air setpoint, C)")
    ap.add_argument("--cooling-min-c", type=float, default=18.0)
    ap.add_argument("--cooling-max-c", type=float, default=27.0)
    ap.add_argument("--cooling-restore-c", type=float, default=22.0)
