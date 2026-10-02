#!/usr/bin/env python3
"""The whole stacks with the real card inside: one harness, one engine, one set of receipts.

Each organism (the four realms and the whole tower of 656, realms/catalog.csv) runs on one clock as in the realm
harness, and the real GPU on this machine is wired into it as one more muscle of its NVIDIA GPU family (a spine family,
so the card sits in every organism): the card serves the pinned request stream (tools/gpu_workload.py), its own
power.draw is heat in the organism's thermal zones and load on its storage sites, and its meter and its requests are
counted in the organism's receipt.

Arms, the same organism, the same seed, the same request stream:
  native  the stacks' own controllers and the card's own firmware, no Omni
  omni    one engine on everything: the bowl law (omnicompass/bowl.py) on every simulated muscle (realms/bowl_arm.py)
          and on the card's two wires (omni_controller/gpu_bowl.py); at 90% of the arm every knob and both wires are
          handed back, and the harness checks they were

Each organism step is --step-s seconds of wall clock (240 steps: 8 minutes at 2 s). The simulated plants are evidence
class S (models); the card's energy and requests are class P (its own meter). The receipt keeps them apart and also
adds them up.

  python3 tools/run_hil.py --out results/hil/run-STAMP [--reps 3] [--step-s 2] [--sim]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realms.harness import catalog, Body, KILL_AT, T95, label  # noqa: E402
from realms.bowl_arm import bowl_apply  # noqa: E402
from realms.presets import ORGANISM_STEPS  # noqa: E402

REALMS = ("compute_ai_cloud", "physics_robotics_autonomous", "energy_facility_industrial", "distribution_specialized")
NAMES = {"compute_ai_cloud": "Compute / AI / Cloud", "physics_robotics_autonomous": "Physics / Robotics / Autonomous",
         "energy_facility_industrial": "Energy / Facility / Industrial", "distribution_specialized": "Distribution / Specialized",
         "organism_656": "The whole tower (656 muscles)"}
SEED0 = 6000
SMI_FIELDS = "timestamp,power.draw,clocks.sm,power.limit,utilization.gpu,temperature.gpu"


def smi(a, *args, check=False):
    return subprocess.run(shlex.split(a.smi) + list(args), capture_output=True, text=True, timeout=30, check=check)


def limit(a):
    return float(smi(a, "-i", str(a.gpu), "--query-gpu=power.limit", "--format=csv,noheader,nounits", check=True).stdout.strip())


def parse_ts(s):
    return datetime.datetime.strptime(s.strip(), "%Y/%m/%d %H:%M:%S.%f").timestamp()


def card_energy(path):
    """Joules from the card's own power.draw samples (trapezoid over their timestamps)."""
    pts = []
    for line in open(path):
        v = [x.strip() for x in line.split(",")]
        try:
            pts.append((parse_ts(v[0]), float(v[1])))
        except (ValueError, IndexError):
            continue
    return sum(0.5 * (p0 + p1) * (t1 - t0) for (t0, p0), (t1, p1) in zip(pts, pts[1:]) if t1 > t0), len(pts)


def last_draw(path, fallback):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 400))
            line = f.read().decode(errors="ignore").strip().splitlines()[-1]
        return float(line.split(",")[1])
    except (OSError, ValueError, IndexError):
        return fallback


def groups():
    rows = catalog()
    g = {r: [x for x in rows if r in x["realms"].split(";")] for r in REALMS}
    g["organism_656"] = rows
    return g


def run_arm(a, name, rows, seed, arm, d, slo_ms, start_w):
    d.mkdir(parents=True, exist_ok=True)
    body = Body(rows, seed)
    for f in ("kill",):
        (d / f).unlink(missing_ok=True)
    smi(a, "-i", str(a.gpu), "-rgc")
    w0 = limit(a)
    sampler = subprocess.Popen(shlex.split(a.smi) + ["-i", str(a.gpu), f"--query-gpu={SMI_FIELDS}", "--format=csv,noheader,nounits",
                                                     "-lms", "200"], stdout=open(d / "smi.csv", "w"), stderr=subprocess.DEVNULL)
    dur = ORGANISM_STEPS * a.step_s
    wl = [sys.executable, str(ROOT / "tools" / "gpu_workload.py"), "run", "--calib-file", str(a.out / "calib.json"),
          "--out", str(d), "--device", f"cuda:{a.gpu}", "--duration", str(dur), "--drain", str(a.drain)]
    if a.sim:
        wl.append("--sim")
    work = subprocess.Popen(wl, stdout=open(d / "workload.log", "w"), stderr=subprocess.STDOUT)
    gov = None
    if arm == "omni":
        gov = subprocess.Popen([sys.executable, "-m", "omni_controller.gpu_bowl", "--mode", "cap", "--gpus", str(a.gpu),
                                "--smi", a.smi, "--interval", str(a.interval), "--audit", str(d / "audit.jsonl"),
                                "--kill-file", str(d / "kill"), "--latency-file", str(d / "latency.csv"),
                                "--slo-ms", str(slo_ms), "--floor-w", str(a.floor_w)], cwd=ROOT,
                               stdout=open(d / "governor.log", "w"), stderr=subprocess.STDOUT)
    kill_at = int(KILL_AT * ORGANISM_STEPS)
    writes = after_kill = 0
    restore_ok = True
    last = {}
    t0 = time.time()
    draw = 0.0
    for k in range(ORGANISM_STEPS):
        body.couple()
        if arm == "omni":
            if k == kill_at:
                (d / "kill").touch()                              # the card's governor hands both wires back
            for p, knob in zip(body.plants, body.knobs):
                if k >= kill_at:
                    p.override = {}
                    continue
                v = bowl_apply(p, knob)
                if v and v != last.get(id(p)):
                    writes += 1
                last[id(p)] = v
        body.step()
        draw = last_draw(d / "smi.csv", draw)
        body.src_w += draw; body.sz_w += draw; body.all_w += draw      # the card's watts in the organism
        wait = t0 + (k + 1) * a.step_s - time.time()
        if wait > 0:
            time.sleep(wait)
    for p in body.plants:
        p.finalize()
        restore_ok = restore_ok and (arm != "omni" or p.override == {})
    work.wait()
    gov_exit = None
    if gov is not None:
        (d / "kill").touch(); gov.wait(timeout=120); gov_exit = gov.returncode
    sampler.terminate(); sampler.wait()
    smi(a, "-i", str(a.gpu), "-rgc")
    w1 = limit(a)
    if abs(w1 - start_w) >= 1.0:
        smi(a, "-i", str(a.gpu), "-pl", str(int(start_w)))
    joules, samples = card_energy(d / "smi.csv")
    summ = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else {}
    lat = sorted(float(x.split(",")[1]) for x in list(open(d / "latency.csv"))[1:] if x.strip()) if (d / "latency.csv").exists() else []
    rec = {"organism": name, "arm": arm, "seed": seed,
           "plants": [dict(p.m) for p in body.plants], "sim_writes": writes, "sim_restore_ok": restore_ok,
           "card": {"energy_j": joules, "samples": samples, "served": summ.get("served", 0),
                    "not_served": summ.get("not_served", summ.get("requests", 0) - summ.get("served", 0)),
                    "p95_ms": lat[int(0.95 * (len(lat) - 1))] if lat else None, "limit_start_w": w0, "limit_end_w": w1,
                    "restored": abs(w1 - start_w) < 1.0, "governor_exit": gov_exit},
           "wall_s": round(time.time() - t0, 1)}
    (d / "arm.json").write_text(json.dumps(rec, indent=1))
    return rec


def ci(xs):
    n = len(xs); m = sum(xs) / n
    if n < 2:
        return m, m, m
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)); h = T95.get(n - 1, 2.0) * sd / math.sqrt(n)
    return m, m - h, m + h


def contrast(o, n):
    """Per-seed contrasts: the simulated stacks, the card, and both together (the card as one more plant)."""
    rs = [(a["work"] / b["work"]) if b["work"] else 1.0 for a, b in zip(o["plants"], n["plants"])]
    es, en = sum(p["energy_j"] for p in o["plants"]), sum(p["energy_j"] for p in n["plants"])
    va = sum(p["viol"] for p in o["plants"]) / sum(p["steps"] for p in o["plants"])
    vn = sum(p["viol"] for p in n["plants"]) / sum(p["steps"] for p in n["plants"])
    cw = (o["card"]["served"] / n["card"]["served"]) if n["card"]["served"] else 1.0
    ce = (o["card"]["energy_j"] / n["card"]["energy_j"]) if n["card"]["energy_j"] else 1.0
    w_all = (sum(rs) + cw) / (len(rs) + 1)
    e_all = (es + o["card"]["energy_j"]) / (en + n["card"]["energy_j"])
    sim_w = sum(rs) / len(rs)
    return {"sim": {"primary": sim_w / (es / en) - 1, "work": sim_w - 1, "energy": es / en - 1, "viol_pp": 100 * (va - vn)},
            "card": {"primary": cw / ce - 1, "work": cw - 1, "energy": ce - 1, "viol_pp": 0.0},
            "all": {"primary": w_all / e_all - 1, "work": w_all - 1, "energy": e_all - 1, "viol_pp": 100 * (va - vn)}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=int(os.environ.get("HIL_REPS", 3)))
    ap.add_argument("--step-s", type=float, default=float(os.environ.get("HIL_STEP_S", 2.0)))
    ap.add_argument("--organisms", default=os.environ.get("HIL_ORGANISMS", ",".join(REALMS + ("organism_656",))))
    ap.add_argument("--gpu", type=int, default=int(os.environ.get("GPU", 0)))
    ap.add_argument("--smi", default=os.environ.get("NVIDIA_SMI", "nvidia-smi"))
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--drain", type=float, default=10.0)
    ap.add_argument("--floor-w", type=float, default=float(os.environ.get("ENV_FLOOR_W", 0.0)))
    ap.add_argument("--sim", action="store_true", default=bool(os.environ.get("SIM")))
    ap.add_argument("--workload-args", default=os.environ.get("WORKLOAD_ARGS", ""))
    a = ap.parse_args(argv)
    a.out = Path(a.out); a.out.mkdir(parents=True, exist_ok=True)
    start_w = limit(a)
    cal = [sys.executable, str(ROOT / "tools" / "gpu_workload.py"), "calibrate", "--out", str(a.out), "--device",
           f"cuda:{a.gpu}"] + shlex.split(a.workload_args) + (["--sim"] if a.sim else [])
    subprocess.run(cal, check=True, capture_output=True)
    service = json.loads((a.out / "calib.json").read_text())["service_ms"]
    slo_ms = round(10 * service, 1)
    commit = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    run = {"started": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "commit": commit, "reps": a.reps,
           "step_s": a.step_s, "steps": ORGANISM_STEPS, "seeds": [SEED0 + r for r in range(a.reps)],
           "start_limit_w": start_w, "slo_ms": slo_ms, "sim_card": a.sim}
    g = groups()
    names = [n for n in a.organisms.split(",") if n]
    res = {}
    for rep in range(a.reps):
        seed = SEED0 + rep
        for i, name in enumerate(names):
            order = ("native", "omni") if (rep + i) % 2 == 0 else ("omni", "native")
            for arm in order:
                print(f"== rep {rep + 1}, {NAMES[name]}, arm {arm}", flush=True)
                res.setdefault(name, {}).setdefault(rep, {})[arm] = run_arm(a, name, g[name], seed, arm,
                                                                            a.out / f"rep-{rep + 1}" / name / arm, slo_ms, start_w)
    problems = []
    for name, reps in res.items():
        for rep, arms in reps.items():
            for arm, r in arms.items():
                if not r["card"]["restored"]:
                    problems.append(f"{name} rep {rep + 1} {arm}: power limit {r['card']['limit_end_w']} W at the end, start {start_w} W")
                if arm == "omni" and not r["sim_restore_ok"]:
                    problems.append(f"{name} rep {rep + 1}: a simulated knob was not handed back")
                if arm == "omni" and r["card"]["governor_exit"] not in (0,):
                    problems.append(f"{name} rep {rep + 1}: the card's governor exited {r['card']['governor_exit']}")
    L = ["# The whole stacks with the real card inside", "",
         f"Run {run['started']}, commit `{commit[:12]}`, {a.reps} paired repetition(s), seeds {run['seeds']}, "
         f"{ORGANISM_STEPS} steps of {a.step_s} s per arm. Card: {'SIMULATED (fake nvidia-smi)' if a.sim else 'the real GPU, its own meter'}; "
         f"start power limit {start_w} W; response-time line {slo_ms} ms (ten bare service times). One engine on everything "
         "in the Omni arm: the bowl law on every simulated muscle and on the card's two wires. Harness `tools/run_hil.py`.", "",
         "The simulated stacks are models (evidence S). The card's energy and requests are its own meter (evidence P). "
         "Work per energy: (work Omni / work native) / (energy Omni / energy native) - 1; for the stacks work is the mean "
         "over plants of each plant's ratio; *both* counts the card as one more plant and adds its joules.", "",
         "## Omni against native, by organism (mean over repetitions, 95% interval when there are two or more)", "",
         "| Organism | Part | Label | Work per energy | Work | Energy | Violations (pp) |", "|---|---|---|---:|---:|---:|---:|"]
    out = {}
    for name in names:
        per = [contrast(res[name][r]["omni"], res[name][r]["native"]) for r in sorted(res[name])]
        out[name] = {}
        for part, pname in (("sim", "stacks (model)"), ("card", "card (meter)"), ("all", "both")):
            xs = [p[part] for p in per]
            m = {k: ci([x[k] for x in xs]) for k in ("primary", "work", "energy", "viol_pp")}
            lab = label(xs) if len(xs) >= 2 else "ONE REPETITION (no label)"
            out[name][part] = {"label": lab, **{k: list(v) for k, v in m.items()}}
            f = lambda k, s=100.0, u="%": f"{s * m[k][0]:+.2f}{u}" + (f" ({s * m[k][1]:+.2f} to {s * m[k][2]:+.2f})" if len(xs) > 1 else "")
            L.append(f"| {NAMES[name]} | {pname} | {lab} | {f('primary')} | {f('work')} | {f('energy')} | {f('viol_pp', 1.0, '')} |")
    L += ["", "## The card's receipts, by arm", "", "| Organism | Rep | Arm | Card energy (J) | Requests served | Not served | p95 (ms) | Limit start → end (W) | Governor exit |",
          "|---|---:|---|---:|---:|---:|---:|---|---|"]
    for name in names:
        for rep in sorted(res[name]):
            for arm in ("native", "omni"):
                c = res[name][rep][arm]["card"]
                L.append(f"| {NAMES[name]} | {rep + 1} | {arm} | {c['energy_j']:.0f} | {c['served']} | {c['not_served']} | "
                         f"{c['p95_ms'] if c['p95_ms'] is None else round(c['p95_ms'], 1)} | {c['limit_start_w']} → {c['limit_end_w']} | {c['governor_exit']} |")
    L += ["", "## Validity", ""] + ([f"- {p}" for p in problems] or ["- Every arm ended with the card at its start limit and its own clock range; every simulated knob was handed back; the card's governor exited cleanly."])
    L += ["", "Raw: every arm's `arm.json`, `smi.csv` (the card's own samples), `latency.csv`, `requests.csv`, `audit.jsonl`; checksums in `SHA256SUMS.txt`."]
    (a.out / "HIL.md").write_text("\n".join(L) + "\n")
    (a.out / "HIL.json").write_text(json.dumps({"run": run, "results": out, "problems": problems}, indent=1) + "\n")
    sums = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(a.out)}" for p in sorted(a.out.rglob("*"))
            if p.is_file() and p.name != "SHA256SUMS.txt"]
    (a.out / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    print("\n".join(L))
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
