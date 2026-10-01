"""End-to-end self-pilot: the shipped controller (omni_controller), capture schema (kube_capture.sh) and scorer
(pilot/score.py) run together against a simulated cluster, exactly as a user would run them against a real one.

The simulated cluster answers the controller's kubectl reads (nodes, pods, kubectl top, HPAs) from a 15-second plant
(fleet/harness.py workloads, request packing, node boot delay, power), applies its HPA patches, and applies node-pool
resizes issued through --node-scale-cmd. Baseline day: HPA at its configured target with the Cluster Autoscaler.
Omni-Compass day: the same traffic, controller in nodepool mode, Cluster Autoscaler off. Both days are captured every
15 s in the kube_capture.sh schema and scored with pilot/score.py using the plant's power. Simulation, not a real cluster.
"""
import argparse, copy, csv, json, math, sys, tempfile
from pathlib import Path
from unittest import mock
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet.harness import make_scenario, hpa_step, BOOT_TICKS, TICK
from fleet.sim import _cluster_autoscaler, ALLOC
from omni_controller.controller import Controller, parser
from pilot.score import main as score

FIELDS = ["timestamp", "elapsed_seconds", "nodes_ready", "nodes_total", "alloc_cpu_m", "req_cpu_m", "used_cpu_m", "pods_pending",
          "hpa_count", "hpa_current_replicas", "hpa_desired_replicas", "power_w"]


class SimCluster:
    def __init__(self, seed, days=1.0, autoscaler="ca"):
        scn = make_scenario("web", seed)
        rng = np.random.default_rng(seed + 1)
        reps = int(math.ceil(days * 86400 / TICK / len(scn.clusters[0].workloads[0].demand)))
        for w in scn.clusters[0].workloads:
            w.demand = np.tile(w.demand, reps) * (1 + 0.03 * rng.standard_normal(len(w.demand) * reps)).clip(0.5, 1.5)
            w.target = 0.70; w.desired = w.replicas
        self.scn, self.c, self.t = scn, scn.clusters[0], 0
        self.steps = int(days * 86400 / TICK); self.autoscaler = autoscaler; self.rows = []

    def tick(self):
        c, p, t = self.c, self.c.pool, self.t
        p.booting = [b - 1 for b in p.booting]; p.nodes += sum(1 for b in p.booting if b <= 0); p.booting = [b for b in p.booting if b > 0]
        alloc = p.nodes * p.cores * ALLOC; reqs = sum(w.replicas * w.request for w in c.workloads)
        frac = min(1.0, alloc / reqs) if reqs > 0 else 1.0; used = 0.0
        for w in c.workloads:
            capw = w.replicas * w.request * frac; srv = min(w.demand[t] + w.backlog, capw)
            w.backlog = w.demand[t] + w.backlog - srv; used += srv
            w.metric = min(1.0, srv / max(w.replicas * w.request, 1e-9))
        c.pending, c.reqs, c.alloc, c.used = max(0.0, reqs - alloc), reqs, alloc, used
        util = min(1.0, used / max(alloc, 1e-9))
        kw = (p.nodes * (p.idle_kw + p.dyn_kw * util) + len(p.booting) * p.idle_kw) * self.scn.pue
        pending_pods = int(sum(max(0, w.replicas - int(w.replicas * frac)) for w in c.workloads))
        for w in c.workloads:
            before = w.replicas; hpa_step(w, w.target); w.desired = w.replicas; w.current = before
        if self.autoscaler == "ca":
            _cluster_autoscaler(c)
        self.rows.append(["", t * TICK, p.nodes, p.nodes + len(p.booting), int(alloc / ALLOC * 1000), int(reqs * 1000), int(used * 1000),
                          pending_pods, len(c.workloads), sum(w.current for w in c.workloads), sum(w.desired for w in c.workloads), kw * 1000])
        self.t += 1

    def resize(self, n):
        p = self.c.pool; cur = p.nodes + len(p.booting); n = max(p.min_nodes, min(p.max_nodes, n))
        if n > cur:
            p.booting += [BOOT_TICKS] * (n - cur)
        elif n < cur:
            k = cur - n; cancel = min(k, len(p.booting)); p.booting = p.booting[cancel:]; p.nodes = max(p.min_nodes, p.nodes - (k - cancel))

    def write_capture(self, path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f); w.writerow(FIELDS); w.writerows(self.rows)


class SimKube:
    """Answers the controller's kubectl calls from SimCluster."""
    def __init__(self, sim, audit):
        self.sim, self.audit, self.dry_run = sim, audit, False

    def get(self, *args):
        c, p = self.sim.c, self.sim.c.pool
        if args[:2] == ("get", "nodes"):
            return {"items": [{"metadata": {"name": f"n{i}"}, "status": {"allocatable": {"cpu": str(p.cores)},
                               "conditions": [{"type": "Ready", "status": "True"}]}} for i in range(p.nodes)]}
        if args[:2] == ("get", "pods"):
            frac = min(1.0, c.alloc / c.reqs) if c.reqs > 0 else 1.0; items = []
            for w in c.workloads:
                run = int(w.replicas * frac)
                items += [{"status": {"phase": "Running"}, "spec": {"containers": [{"resources": {"requests": {"cpu": f"{int(w.request * 1000)}m"}}}]}}] * run
                items += [{"status": {"phase": "Pending"}, "spec": {"containers": [{"resources": {"requests": {"cpu": f"{int(w.request * 1000)}m"}}}]}}] * (w.replicas - run)
            return {"items": items}
        if args[:2] == ("top", "nodes"):
            per = c.used / max(p.nodes, 1)
            return "\n".join(f"n{i} {int(per * 1000)}m 1% 1Gi 1%" for i in range(p.nodes))
        if args[:2] == ("get", "hpa"):
            return {"items": [{"metadata": {"name": w.name, "namespace": "default", "annotations": getattr(w, "ann", {})},
                               "spec": {"metrics": [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": int(round(w.target * 100))}}}]},
                               "status": {"currentReplicas": w.replicas, "desiredReplicas": w.desired}} for w in c.workloads]}
        raise ValueError(args)

    def write(self, args, why):
        self.audit({"write": list(args), "why": why, "dry_run": False})
        w = next(x for x in self.sim.c.workloads if x.name == args[2])
        if args[0] == "patch":
            w.target = json.loads(args[args.index("-p") + 1])[0]["value"] / 100.0
        elif args[0] == "annotate":
            kv = args[-1]
            w.ann = getattr(w, "ann", {})
            if kv.endswith("-"):
                w.ann.pop(kv[:-1], None)
            else:
                k, v = kv.split("=", 1); w.ann[k] = v


def run_day(seed, omni, out, days, headroom=0.5):
    sim = SimCluster(seed, days, autoscaler="none" if omni else "ca")
    if omni:
        a = parser().parse_args(["--mode", "nodepool", "--interval", "0", "--audit", str(out / "audit.jsonl"), "--kill-file", str(out / "kill"),
                                 "--node-scale-cmd", "SIMSCALE {n}", "--min-nodes", str(sim.c.pool.min_nodes), "--max-nodes", str(sim.c.pool.max_nodes),
                                 "--headroom", str(headroom)])
        ctl = Controller(a); ctl.k = SimKube(sim, ctl.audit)
        real_run = __import__("subprocess").run

        def fake_run(cmd, *k, **kw):
            if isinstance(cmd, list) and cmd and cmd[0] == "SIMSCALE":
                sim.resize(int(cmd[1])); return None
            return real_run(cmd, *k, **kw)
        with mock.patch("omni_controller.controller.subprocess.run", side_effect=fake_run):
            while sim.t < sim.steps:
                sim.tick()
                sim.c.alloc = sim.c.pool.nodes * sim.c.pool.cores * ALLOC
                if sim.t % 4 == 0:
                    ctl.step()
                else:
                    ctl.floor_step()
    else:
        while sim.t < sim.steps:
            sim.tick()
    path = out / ("omni.csv" if omni else "baseline.csv"); sim.write_capture(path)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, default=424242); ap.add_argument("--days", type=float, default=1.0)
    ap.add_argument("--headroom", type=float, default=0.5); ap.add_argument("--out", default=""); a = ap.parse_args(argv)
    out = Path(a.out or tempfile.mkdtemp()); out.mkdir(parents=True, exist_ok=True)
    base = run_day(a.seed, False, out, a.days); om = run_day(a.seed, True, out, a.days, a.headroom)
    res = score(["--baseline", str(base), "--omni", str(om), "--out", str(out / "SCORE.json")])
    n_writes = sum(1 for l in open(out / "audit.jsonl") if '"write"' in l)
    print(f"controller decisions logged: {sum(1 for _ in open(out / 'audit.jsonl'))}, writes: {n_writes}")
    return res, out


if __name__ == "__main__":
    main()
