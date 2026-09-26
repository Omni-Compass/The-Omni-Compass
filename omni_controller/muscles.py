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
              scaling_max_freq, or `cpupower frequency-set -u {khz}kHz`); kill runs it with the maximum frequency
  gpu         hardware connector. pull: --gpu-query-cmd prints "watts,celsius" (e.g. `nvidia-smi
              --query-gpu=power.draw,temperature.gpu --format=csv,noheader,nounits`); GPU temperature / --gpu-temp-limit
              feeds the heat sense; push: --gpu-power-cmd with {w}, the power limit = max limit x power cap
              (e.g. `nvidia-smi -pl {w}`); kill restores the maximum limit
  Hardware connectors are off unless their commands are given (not available on CI runners); the mechanism is the same.
"""
from __future__ import annotations

import csv, json, math, shlex, subprocess, time
import re

CPU_ANN = "omnicompass.io/original-cpu-limit"
PAUSE_ANN = "omnicompass.io/paused-by-omni"
BATCH_LABEL = "omnicompass.io/batch=true"


def milli(v):
    v = str(v)
    return float(v[:-1]) if v.endswith("m") else float(v) * 1000.0


def ref(s):
    ns, name = s.split("/", 1)
    return ns, name


class Muscles:
    def __init__(self, k, a, audit):
        self.k, self.a, self.audit = k, a, audit
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
            p95 = latency_p95(lf, self.a.latency_window_s)
            if p95 == p95:
                o["latency_p95_ms"] = p95
                o["latency_pressure"] = max(0.0, p95 / self.a.slo_ms - 1.0)
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
        cmd = template.format(khz=int(value), w=int(value))
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

    def _hardware(self, cap, obs):
        cap = 1.0 if not obs.get("slo_clean", True) else max(self.a.cap_min, min(1.0, cap))
        if obs.get("security_block", 0.0) > 0.5:
            cap = min(cap, getattr(self, "_last_cap", 1.0))  # shield I1: no expansion during a security hold
        if abs(cap - getattr(self, "_last_cap", 1.0)) < 0.02:
            return
        if getattr(self.a, "cpufreq_cmd", "") and self.a.cpu_max_khz:
            self._hw(self.a.cpufreq_cmd, self.a.cpu_max_khz * cap, f"cpu_pstate: frequency ceiling {int(self.a.cpu_max_khz * cap)} kHz (cap {cap:.3f})")
        if getattr(self.a, "gpu_power_cmd", "") and self.a.gpu_max_w:
            self._hw(self.a.gpu_power_cmd, self.a.gpu_max_w * cap, f"gpu: power limit {int(self.a.gpu_max_w * cap)} W (cap {cap:.3f})")
        self._last_cap = cap

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
        jobs = self.k.get("get", "jobs", "-A", "-l", BATCH_LABEL, "-o", "json")["items"]
        held = sorted((j for j in jobs if j["spec"].get("suspend")), key=lambda j: j["metadata"].get("creationTimestamp", ""))
        if held:
            j = held[0]; ns, name = j["metadata"]["namespace"], j["metadata"]["name"]
            self.k.write(["patch", "job", name, "-n", ns, "--type=merge", "-p", json.dumps({"spec": {"suspend": False}})],
                         "batch: admit held job (headroom)")

    # ---- kill -------------------------------------------------------------------------------------------------------
    def restore(self):
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
    ap.add_argument("--slo-clear", type=int, default=3, help="decisions the SLO must stay met before densifying or capping again")
    ap.add_argument("--thermal-model", action="store_true", help="heat muscle: thermal state from the harness heat law")
    ap.add_argument("--security-configmap", default="", help="ns/name of a ConfigMap whose key 'hold' signals a security hold")
    ap.add_argument("--rollout-guard", default="", help="ns/name[,ns/name]: rollout muscle pauses, resumes, undoes")
    ap.add_argument("--batch", action="store_true", help="batch muscle: admit held Jobs labelled " + BATCH_LABEL)
    ap.add_argument("--batch-load-max", type=float, default=0.8)
    ap.add_argument("--batch-power-max", type=float, default=0.9)
    ap.add_argument("--rapl-cmd", default="", help="cpu_pstate pull: prints CPU package watts")
    ap.add_argument("--cpufreq-cmd", default="", help="cpu_pstate push: command template with {khz}")
    ap.add_argument("--cpu-max-khz", type=float, default=0.0)
    ap.add_argument("--gpu-query-cmd", default="", help="gpu pull: prints 'watts,celsius'")
    ap.add_argument("--gpu-power-cmd", default="", help="gpu push: command template with {w}")
    ap.add_argument("--gpu-max-w", type=float, default=0.0)
    ap.add_argument("--gpu-temp-limit", type=float, default=83.0, help="GPU temperature treated as thermal 1.0")
