"""The GPU test without a GPU: Omni-Compass's own GPU governor (omni_controller/gpu_governor.py, its command-line defaults)
against a modelled NVIDIA card, in virtual time. A preview, not evidence: every energy number here comes from the model
below, not from a meter. The hardware answer is scripts/gpu_paired.sh on a real card.

  python3 tools/gpu_physics_sim.py                      # 10 paired repetitions, both card models, table to stdout
  python3 tools/gpu_physics_sim.py --reps 5 --out results/gpu/sim --gov "--min-share 0 --util-gate 0"   # other settings

The card (an assumption, stated):
  idle draw      40 W while no request is being served
  busy draw      P(s) = 80 + 220 s^gamma W at speed s (1 = full clock); 300 W at full clock, the start limit
  power limit L  below 300 W the card slows to the speed where P(s) = L, as real cards do by lowering clocks
  heat           first order toward 30 C + 0.12 C/W x draw, time constant 20 s
gamma is how much the top of the clock range costs: 3 when voltage falls with clock (good for capping), 1.5 when the
card already sits near its voltage floor (hard for capping). Both are run; a real card lies somewhere between.

The workload is tools/gpu_workload.py's: Poisson arrivals at 30, 60, 80, 30, 60, 30% of full-speed capacity, seed
20260928 + repetition, one server first come first served, 50 ms per request at full speed, 600 s plus 30 s drain; the
response-time target is ten service times (500 ms), as scripts/gpu_paired.sh sets it. The governor decides at its own
interval (default 2 s) from the modelled card's nvidia-smi readings and the response-time file, exactly as on hardware.
"""
from __future__ import annotations

import argparse, json, math, os, random, shlex, statistics, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.gpu_governor import GpuGovernor, parser as gov_parser

START, MIN = 300.0, 100.0
P_IDLE, P_STATIC, P_DEMAND = 40.0, 80.0, 300.0
SERVICE_MS, SLO_MS = 50.0, 500.0
PHASES = [0.3, 0.6, 0.8, 0.3, 0.6, 0.3]
DURATION, DRAIN = 600, 30
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
       14: 2.145, 19: 2.093, 29: 2.045}

SMI = '''#!/usr/bin/env python3
import json, os, sys
p = os.environ["PHYS_STATE"]; st = json.load(open(p)); a = sys.argv[1:]
if "-pl" in a:
    st["limit"] = float(a[a.index("-pl") + 1]); json.dump(st, open(p, "w")); print("ok"); sys.exit(0)
f = [x for x in a if x.startswith("--query-gpu=")][0].split("=", 1)[1].split(",")
if any("reasons" in x for x in f): sys.exit(2)
v = {"index": 0, "power.draw": st["draw"], "temperature.gpu": st["temp"], "utilization.gpu": round(100 * st["util"]),
     "power.limit": st["limit"], "power.min_limit": %s, "clocks.sm": round(1800 * st["speed"]),
     "enforced.power.limit": st["limit"], "power.management": "Enabled", "persistence_mode": "Enabled",
     "power.default_limit": 300, "power.max_limit": 300}
print(", ".join(str(v[x]) for x in f))
''' % MIN


def speed_at(limit, gamma):
    return 1.0 if limit >= P_DEMAND else max(0.05, (limit - P_STATIC) / (P_DEMAND - P_STATIC)) ** (1.0 / gamma)


def busy_power(s, gamma):
    return P_STATIC + (P_DEMAND - P_STATIC) * s ** gamma


def arrivals(seed):
    rng = random.Random(seed); out = []; per = DURATION / len(PHASES)
    for i, share in enumerate(PHASES):
        rate = share / (SERVICE_MS / 1000.0); t = i * per
        while True:
            t += rng.expovariate(rate)
            if t >= (i + 1) * per:
                break
            out.append(t)
    return out


def run(arm, seed, gamma, work, gov_argv):
    """One arm: native (the start limit throughout) or omni (the governor in cap mode). Returns its gauges."""
    tag = f"{arm}-{seed}-{gamma}"
    state, lat = work / f"state-{tag}.json", work / f"latency-{tag}.csv"
    state.write_text(json.dumps({"limit": START, "draw": P_IDLE, "temp": 35.0, "util": 0.0, "speed": 1.0}))
    lat.write_text("elapsed_seconds,latency_ms,ok\n")
    os.environ["PHYS_STATE"] = str(state)
    gov = None
    if arm == "omni":
        a = gov_parser().parse_args(["--mode", "cap", "--smi", str(work / "smi.py"), "--audit", str(work / f"audit-{tag}.jsonl"), "--kill-file", str(work / "no-kill"),
                                     "--latency-file", str(lat), "--slo-ms", str(SLO_MS)] + gov_argv)
        gov = GpuGovernor(a); every = max(1, int(round(a.interval)))
    arr = arrivals(seed); ai = 0; queue = []; energy = 0.0; temp = 35.0; lats = []; limits = []; peak = 0.0
    for sec in range(DURATION + DRAIN):
        st = json.loads(state.read_text()); limit = st["limit"]; limits.append(limit)
        s = speed_at(limit, gamma); pb = busy_power(s, gamma)
        t, end, busy, rows = float(sec), sec + 1.0, 0.0, []
        while t < end:
            while ai < len(arr) and arr[ai] <= t:
                queue.append([arr[ai], SERVICE_MS / 1000.0]); ai += 1
            nxt = arr[ai] if ai < len(arr) else math.inf
            if not queue:
                t = min(end, nxt); continue
            job = queue[0]
            step = min(job[1] / s, end - t, nxt - t)
            job[1] -= step * s; busy += step; t += step
            if job[1] <= 1e-12:
                queue.pop(0); ms = (t - job[0]) * 1000.0; lats.append(ms); rows.append(f"{t:.3f},{ms:.2f},1\n")
        draw = busy * pb + (1 - busy) * P_IDLE
        energy += draw; temp += (30 + 0.12 * draw - temp) / 20.0; peak = max(peak, temp)
        with open(lat, "a") as f:
            f.writelines(rows)
        st.update(draw=round(draw, 2), temp=round(temp, 1), util=busy, speed=s); state.write_text(json.dumps(st))
        if gov and sec < DURATION and sec % every == every - 1:
            gov.step()
    if gov:
        gov.restore()
    lats.sort()
    return {"requests served per kJ": len(lats) / (energy / 1000.0), "GPU energy (J)": energy,
            "GPU mean power (W)": energy / (DURATION + DRAIN), "requests served": len(lats),
            "requests not served": len(arr) - len(lats), "response time, mean (ms)": statistics.mean(lats),
            "response time, 95th percentile (ms)": lats[int(0.95 * len(lats))],
            "response time, 99th percentile (ms)": lats[int(0.99 * len(lats))], "peak temperature (C)": peak,
            "power limit, mean (W)": statistics.mean(limits[:DURATION]), "power-limit writes": gov.writes if gov else 0}


def paired(nat, om, k):
    d = [b[k] - a[k] for a, b in zip(nat, om)]; n = len(d); m = statistics.mean(d)
    h = T95.get(n - 1, 2.0) * statistics.stdev(d) / math.sqrt(n) if n > 1 else float("nan")
    return m, m - h, m + h


def table(gamma, nat, om):
    out = [f"### Card model gamma {gamma:g} ({'voltage falls with clock' if gamma >= 2.5 else 'near its voltage floor'})",
           "", f"{len(nat)} paired repetitions. A change is proven when its 95% interval excludes zero.", "",
           "| Gauge | Native | Omni | Change | 95% interval of the difference |", "|---|---:|---:|---:|---:|"]
    for k in nat[0]:
        n = statistics.mean(x[k] for x in nat); o = statistics.mean(x[k] for x in om); m, lo, hi = paired(nat, om, k)
        pct = f"{100 * (o - n) / n:+.1f}%" if n else "n/a"
        out.append(f"| {k} | {n:.4g} | {o:.4g} | {pct} | {lo:+.4g} to {hi:+.4g} |")
    kj = "requests served per kJ"; p95 = "response time, 95th percentile (ms)"
    m, lo, hi = paired(nat, om, kj)
    base95 = statistics.mean(x[p95] for x in nat); _, _, hi95 = paired(nat, om, p95)
    guard = hi95 <= 0.10 * base95
    word = "better, proven" if lo > 0 else "worse, proven" if hi < 0 else "not proven"
    if lo > 0 and not guard:
        word = "better on energy, fails the service guardrail"
    out += ["", f"Guardrail (preregistered): 95th-percentile response time not above +10%: "
                f"{'held' if guard else 'FAILED'} (upper bound {100 * hi95 / base95:+.1f}%).",
            f"**Model verdict: {word}.**", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--gammas", default="3,1.5")
    ap.add_argument("--gov", default="", help="extra governor arguments, e.g. \"--min-share 0 --util-gate 0\"")
    ap.add_argument("--out", default="", help="folder for GPU_PHYSICS_SIM.md and .json")
    a = ap.parse_args(argv)
    work = Path(tempfile.mkdtemp(prefix="gpu-physics-sim-"))
    (work / "smi.py").write_text(SMI); (work / "smi.py").chmod(0o755)
    gov_argv = shlex.split(a.gov)
    settings = vars(gov_parser().parse_args(["--smi", "x"] + gov_argv))
    report = ["# GPU physics simulation: native against Omni-Compass, modelled card", "",
              "Every number below comes from the card model in tools/gpu_physics_sim.py, not from a meter. It shows what",
              "the governor does to a card that behaves as modelled; the hardware answer is scripts/gpu_paired.sh.", "",
              "Governor settings: " + ", ".join(f"{k} {settings[k]}" for k in ("headroom", "min_share", "util_gate", "util_band", "interval")),
              ""]
    raw = {}
    for gamma in (float(g) for g in a.gammas.split(",")):
        nat = [run("native", 20260928 + r, gamma, work, gov_argv) for r in range(a.reps)]
        om = [run("omni", 20260928 + r, gamma, work, gov_argv) for r in range(a.reps)]
        report.append(table(gamma, nat, om)); raw[str(gamma)] = {"native": nat, "omni": om}
    text = "\n".join(report)
    print(text)
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        (Path(a.out) / "GPU_PHYSICS_SIM.md").write_text(text + "\n")
        (Path(a.out) / "GPU_PHYSICS_SIM.json").write_text(json.dumps({"settings": settings, "reps": a.reps, "raw": raw}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
