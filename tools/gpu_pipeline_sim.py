# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Speed won on the CPU, spent on the GPU: a request served by a CPU stage and then a GPU stage, with Omni-Compass's
speed lock (omni_controller/gpu_governor.py --baseline-file) on the GPU. A preview on a model, not evidence.

  python3 tools/gpu_pipeline_sim.py                       # 10 paired repetitions, both card models
  python3 tools/gpu_pipeline_sim.py --cpu-ms 10 --out results/gpu/sim/pipeline

Each request needs --cpu-ms of CPU work on one core (preparing the input) and then the GPU (tools/gpu_physics_sim.py's
card and workload: 50 ms at full clock, Poisson arrivals at 30/60/80/30/60/30% of GPU capacity). The serving pod's
CPU limit is enforced as Linux does it (CFS bandwidth): a quota of limit x 100 ms of CPU time per 100 ms period; the
pod's work runs at a full core until the period's quota is spent, then waits for the next period. The operator's
--native-limit (0.5 core: 50 ms per 100 ms) throttles bursts; Omni's conveyance (omni_controller/muscles.py convey:
the machine's idle CPU to the serving pods) raises the limit to --conveyed-limit (1 core: never throttled for one
thread). Both stages are first come first served queues.

Arms, paired on the same arrivals:
  native  operator's CPU limit, GPU at its start limit (no Omni)
  speed   CPU conveyed, GPU at its start limit: the speed the CPU muscle wins, handed to the customer
  lock    CPU conveyed, GPU under the speed lock: the speed won is spent on GPU watts, keeping every gauge (mean,
          p95, p99) at least --speed-gain faster than native
The lock's baseline comes from native runs on other seeds (tools/gpu_baseline.py), never from the arms judged.
CPU work is the same core-seconds in every arm (conveyance moves no work, it removes waiting); only GPU energy differs.
"""
from __future__ import annotations

import argparse, json, math, os, shlex, statistics, sys, tempfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.gpu_governor import GpuGovernor, parser as gov_parser
from tools.gpu_physics_sim import SMI, START, P_IDLE, SERVICE_MS, SLO_MS, DURATION, DRAIN, speed_at, busy_power, arrivals, paired
from tools.gpu_baseline import build as build_baseline

DT = 0.001


def run(seed, gamma, work, cpu_ms, cpu_limit, lock_argv=None, tag=""):
    """One arm. lock_argv None: GPU held at its start limit. Returns gauges and the latency rows."""
    state, lat = work / f"state-{tag}.json", work / f"latency-{tag}.csv"
    state.write_text(json.dumps({"limit": START, "draw": P_IDLE, "temp": 35.0, "util": 0.0, "speed": 1.0}))
    lat.write_text("elapsed_seconds,latency_ms,ok\n")
    os.environ["PHYS_STATE"] = str(state)
    gov, every = None, 1
    if lock_argv is not None:
        a = gov_parser().parse_args(["--mode", "cap", "--smi", str(work / "smi.py"), "--audit", str(work / f"audit-{tag}.jsonl"),
                                     "--kill-file", str(work / "no-kill"), "--latency-file", str(lat),
                                     "--slo-ms", str(SLO_MS)] + lock_argv)
        gov = GpuGovernor(a); every = max(1, int(round(a.interval))); vt = {"t": 0.0}; gov.clock = lambda: vt["t"]
    arr = arrivals(seed); ai = 0
    cpu_q, gpu_q = deque(), deque()
    quota, used = cpu_limit * 0.1, 0.0          # CFS: seconds of CPU per 100 ms period
    per = int(round(0.1 / DT))
    energy = 0.0; temp = 35.0; lats = []; rows_all = []; limits = []
    steps = int(round(1.0 / DT))
    for sec in range(DURATION + DRAIN):
        st = json.loads(state.read_text()); limit = st["limit"]; limits.append(limit)
        s = speed_at(limit, gamma); pb = busy_power(s, gamma)
        busy = 0.0; rows = []
        for k in range(steps):
            t = sec + k * DT
            while ai < len(arr) and arr[ai] <= t:
                cpu_q.append([arr[ai], cpu_ms / 1000.0]); ai += 1
            if k % per == 0:
                used = 0.0                          # a new CFS period
            if cpu_q and used < quota - 1e-12:
                j = cpu_q[0]; j[1] -= DT; used += DT
                if j[1] <= 1e-12:
                    cpu_q.popleft(); gpu_q.append([j[0], SERVICE_MS / 1000.0])
            if gpu_q:
                j = gpu_q[0]; j[1] -= DT * s; busy += DT
                if j[1] <= 1e-12:
                    gpu_q.popleft(); ms = (t + DT - j[0]) * 1000.0; lats.append(ms)
                    rows.append(f"{t + DT:.3f},{ms:.2f},1\n"); rows_all.append((t + DT, ms, True))
        draw = busy * pb + (1 - busy) * P_IDLE
        energy += draw; temp += (30 + 0.12 * draw - temp) / 20.0
        with open(lat, "a") as f:
            f.writelines(rows)
        st.update(draw=round(draw, 2), temp=round(temp, 1), util=busy, speed=s); state.write_text(json.dumps(st))
        if gov and sec < DURATION and sec % every == every - 1:
            vt["t"] = sec + 1.0; gov.step()
    if gov:
        gov.restore()
    lats.sort()
    g = {"requests served per kJ (GPU)": len(lats) / (energy / 1000.0), "GPU energy (J)": energy,
         "requests served": len(lats), "requests not served": len(arr) - len(lats),
         "response time, mean (ms)": statistics.mean(lats), "response time, 95th percentile (ms)": lats[int(0.95 * len(lats))],
         "response time, 99th percentile (ms)": lats[int(0.99 * len(lats))],
         "GPU power limit, mean (W)": statistics.mean(limits[:DURATION]), "power-limit writes": gov.writes if gov else 0}
    return g, rows_all


def compare(title, nat, arm, speed_gain, lock=False):
    out = [f"#### {title}", "", "| Gauge | Native | This arm | Change | 95% interval of the difference |", "|---|---:|---:|---:|---:|"]
    for k in nat[0]:
        n = statistics.mean(x[k] for x in nat); o = statistics.mean(x[k] for x in arm); m, lo, hi = paired(nat, arm, k)
        pct = f"{100 * (o - n) / n:+.1f}%" if n else "n/a"
        out.append(f"| {k} | {n:.4g} | {o:.4g} | {pct} | {lo:+.4g} to {hi:+.4g} |")
    if lock:
        held = []
        for k in ("response time, mean (ms)", "response time, 95th percentile (ms)", "response time, 99th percentile (ms)"):
            n = statistics.mean(x[k] for x in nat); _, _, hi = paired(nat, arm, k)
            held.append((k.split(", ")[1].split(" (")[0], 100 * hi / n))
        ok = all(h <= -100 * speed_gain for _, h in held)
        out += ["", f"Speed lock (every gauge at least {100 * speed_gain:g}% faster than native, upper end of its 95% interval): "
                    + ", ".join(f"{name} {h:+.1f}%" for name, h in held) + f" -> **{'HELD' if ok else 'NOT HELD'}**."]
    return "\n".join(out + [""])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--gammas", default="3,1.5")
    ap.add_argument("--cpu-ms", type=float, default=20.0, help="CPU work per request on one core (ms)")
    ap.add_argument("--native-limit", type=float, default=0.5, help="operator's CPU limit of the serving pod (cores)")
    ap.add_argument("--conveyed-limit", type=float, default=1.0, help="the pod's CPU limit under conveyance (cores)")
    ap.add_argument("--calib-runs", type=int, default=3)
    ap.add_argument("--gov", default="", help="extra governor arguments for the lock arm")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    work = Path(tempfile.mkdtemp(prefix="gpu-pipeline-sim-"))
    (work / "smi.py").write_text(SMI); (work / "smi.py").chmod(0o755)
    # the baseline: native runs on seeds the comparison never uses (latency at the start limit does not depend on gamma)
    calib = [run(900001 + i, 3.0, work, a.cpu_ms, a.native_limit, tag=f"calib-{i}")[1] for i in range(a.calib_runs)]
    base = build_baseline(calib); bf = work / "baseline.json"; bf.write_text(json.dumps(base))
    lock_argv = ["--baseline-file", str(bf)] + shlex.split(a.gov)
    settings = vars(gov_parser().parse_args(["--smi", "x"] + lock_argv))
    report = ["# Speed won on the CPU, spent on the GPU (model)", "",
              f"CPU work {a.cpu_ms:g} ms per request; pod CPU limit {a.native_limit:g} core native, {a.conveyed_limit:g} "
              f"conveyed. GPU as tools/gpu_physics_sim.py. Baseline from {a.calib_runs} native runs on other seeds.",
              "Lock settings: " + ", ".join(f"{k} {settings[k]}" for k in ("speed_gain", "lock_margin", "lock_step",
                                                                          "lock_window_s", "lock_floor", "interval")),
              "Every number comes from the model in this file and tools/gpu_physics_sim.py, not from a meter.", ""]
    raw = {}
    for gamma in (float(x) for x in a.gammas.split(",")):
        nat, spd, lck = [], [], []
        for r in range(a.reps):
            seed = 20260928 + r
            nat.append(run(seed, gamma, work, a.cpu_ms, a.native_limit, tag=f"n-{gamma}-{r}")[0])
            spd.append(run(seed, gamma, work, a.cpu_ms, a.conveyed_limit, tag=f"s-{gamma}-{r}")[0])
            lck.append(run(seed, gamma, work, a.cpu_ms, a.conveyed_limit, lock_argv, tag=f"l-{gamma}-{r}")[0])
        report.append(f"### Card model gamma {gamma:g}, {a.reps} paired repetitions\n")
        report.append(compare("CPU muscle only (speed handed to the customer)", nat, spd, settings["speed_gain"]))
        report.append(compare("CPU muscle + GPU speed lock (speed spent on watts)", nat, lck, settings["speed_gain"], lock=True))
        raw[str(gamma)] = {"native": nat, "speed": spd, "lock": lck}
    text = "\n".join(report); print(text)
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        (Path(a.out) / "GPU_PIPELINE_SIM.md").write_text(text + "\n")
        (Path(a.out) / "GPU_PIPELINE_SIM.json").write_text(json.dumps({"settings": settings, "args": vars(a), "baseline": base,
                                                                      "raw": raw}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
