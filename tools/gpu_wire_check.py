#!/usr/bin/env python3
"""The wire check: before any test, prove both of the card's wires are connected the right way round.

Run as root on the machine with the card (scripts/gpu_rented_run.sh runs it first, and stops if it fails):

    sudo python3 tools/gpu_wire_check.py [--gpu 0] [--smi nvidia-smi]

  1 read        every meter answers: watts, temperature, utilization, power limit, clock, top clock
  2 snapshot    the starting power limit, read once
  3 up wire     with the card busy, lock the clock ceiling low: the clock must come down under it; reset it: the clock
                must come back up (the ceiling is followed, in the right direction)
  4 down wire   set the power limit lower: the card must report it; set it back: the card must report the start
  5 restore     clocks reset and the start limit, read back
  6 stop        the two-wire governor, stopped by its stop signal, hands both wires back
  7 other writer someone else moves the limit while the governor runs: it must stop writing, leave that value alone and
                exit 5
Each step prints PASS or FAIL with the wire, the step and what the card said; the first failure stops the check (exit 1)
and leaves the card at its start values. Exit 0: wired right.
"""
from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omni_controller.gpu_governor import query  # noqa: E402
from omni_controller.gpu_bowl import query_top_clock, query_min_clock, smi_run  # noqa: E402

LOAD = ("import torch,time,sys\n"
        "d=torch.device(sys.argv[1]); a=torch.randn(4096,4096,device=d); t=time.time()\n"
        "while time.time()-t<float(sys.argv[2]):\n"
        "    b=a@a; torch.cuda.synchronize()\n")


class Fail(Exception):
    pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--smi", default=os.environ.get("NVIDIA_SMI", "nvidia-smi"))
    ap.add_argument("--settle", type=float, default=float(os.environ.get("WIRE_SETTLE", 4.0)))
    ap.add_argument("--sim", action="store_true", default=bool(os.environ.get("SIM")), help="no load is started (fake card)")
    a = ap.parse_args(argv)
    g, smi = a.gpu, a.smi
    start = None
    load = None

    def say(step, ok, what):
        print(f"{'PASS' if ok else 'FAIL'}  {step}: {what}", flush=True)
        if not ok:
            raise Fail(step)

    def read():
        s = query(smi, [g], False)
        return s[g] if s else None

    def busy(seconds):
        nonlocal load
        if a.sim:
            return
        load = subprocess.Popen([sys.executable, "-c", LOAD, f"cuda:{g}", str(seconds)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)

    rc_all = 0
    try:
        r = read(); top = query_top_clock(smi, g)
        say("1 read", r is not None and top is not None,
            f"draw {r['draw']} W, temp {r['temp']} C, util {r['util']:.2f}, limit {r['limit']} W, clock {r['clock_mhz']} MHz, "
            f"top clock {top} MHz" if r and top else "nvidia-smi did not answer every meter")
        start = r["limit"]
        say("2 snapshot", start > 0, f"start power limit {start} W")

        busy(4 * a.settle + 6)
        low, floor = int(0.6 * top), query_min_clock(smi, g)
        rc, err = smi_run(smi, ["-i", str(g), "-lgc", f"{floor},{low}"])
        say("3 up wire (lock)", rc == 0, f"nvidia-smi -lgc {floor},{low} returned {rc} {err}".strip())
        time.sleep(a.settle)
        c_low = read()["clock_mhz"]
        say("3 up wire (follows down)", c_low <= low + 30, f"ceiling {low} MHz, the card's clock {c_low} MHz")
        rc, err = smi_run(smi, ["-i", str(g), "-rgc"])
        say("3 up wire (reset)", rc == 0, f"nvidia-smi -rgc returned {rc} {err}".strip())
        time.sleep(a.settle)
        c_up = read()["clock_mhz"]
        say("3 up wire (follows up)", c_up > c_low + 30, f"after reset the card's clock {c_up} MHz, under the lock {c_low} MHz")

        mn = read().get("min", 0.0)
        lower = int(max(mn, 0.8 * start))
        rc, err = smi_run(smi, ["-i", str(g), "-pl", str(lower)])
        say("4 down wire (lower)", rc == 0, f"nvidia-smi -pl {lower} returned {rc} {err}".strip())
        back = read()["limit"]
        say("4 down wire (read back)", abs(back - lower) < 1.0, f"asked {lower} W, the card reports {back} W")
        rc, err = smi_run(smi, ["-i", str(g), "-pl", str(int(start))])
        back = read()["limit"]
        say("4 down wire (back up)", rc == 0 and abs(back - start) < 1.0, f"asked {int(start)} W, the card reports {back} W")

        smi_run(smi, ["-i", str(g), "-rgc"])
        back = read()["limit"]
        say("5 restore", abs(back - start) < 1.0, f"clocks reset, limit {back} W (start {start} W)")

        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, NVIDIA_SMI=smi)
            cmd = [sys.executable, "-m", "omni_controller.gpu_bowl", "--mode", "cap", "--gpus", str(g), "--smi", smi,
                   "--interval", "0.5", "--audit", f"{d}/a.jsonl", "--kill-file", f"{d}/kill", "--down-gain", "0.5"]
            p = subprocess.Popen(cmd, cwd=ROOT, env=env)
            time.sleep(3.0)
            p.send_signal(signal.SIGTERM); p.wait(timeout=30)
            back = read()["limit"]
            say("6 stop", p.returncode == 0 and abs(back - start) < 1.0,
                f"governor exit {p.returncode}, limit after stop {back} W (start {start} W)")

            p = subprocess.Popen(cmd[:-6] + ["--audit", f"{d}/b.jsonl", "--kill-file", f"{d}/kill2", "--down-gain", "0.5"],
                                 cwd=ROOT, env=env)
            time.sleep(2.0)
            other = int(max(mn, 0.9 * start))
            smi_run(smi, ["-i", str(g), "-pl", str(other)])
            time.sleep(2.0)
            Path(f"{d}/kill2").touch(); p.wait(timeout=30)
            back = read()["limit"]
            say("7 other writer", p.returncode == 5 and abs(back - other) < 1.0,
                f"governor exit {p.returncode} (5 expected), limit left at {back} W (the other writer set {other} W)")
        print("WIRED RIGHT: both wires follow, read back and go home.", flush=True)
    except Fail as e:
        print(f"WIRE CHECK FAILED at step {e}. Nothing will run until this is fixed.", flush=True)
        rc_all = 1
    finally:
        if load is not None:
            load.kill()
        smi_run(smi, ["-i", str(g), "-rgc"])
        if start:
            smi_run(smi, ["-i", str(g), "-pl", str(int(start))])
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
