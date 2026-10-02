# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Omni-Compass on one GPU through two wires: the bowl law (omnicompass/bowl.py) on a real card.

The card keeps its own control: NVIDIA's firmware still boosts and still protects the chip. Omni holds two settings the
card already accepts, and nothing else:
  up wire    the clock ceiling: how high boost may climb (nvidia-smi -lgc MIN,MAX; -rgc resets it)
  down wire  the power limit: the lid above what that ceiling draws (nvidia-smi -pl W)

Every decision (--interval seconds):
  read      nvidia-smi: power.draw, temperature, utilization, power.limit, clocks.sm; the workload's response times
  position  the service as one place in its bowl, 0 calm to 1 the line: response time only (p95 over the last
            --latency-window-s, between a tenth of the line, the bare service time, and the line). A card that is busy
            is doing its work; being busy is not a breach and is not read as one
  native    what the card does on its own, learned from its own meter before the bowl may lower anything: while the
            ceiling is at the top and the card is busy, its clock and its draw (the clock its own power limit holds it
            at, and what that costs). Until --learn-samples busy readings are in, the ceiling stays at the top
  race      while the card is saturated (utilization at or over --race-util: work is waiting), the ceiling goes to the
            top and the lid to the start limit, so a burst is served at full speed; the bowl paces only the slack
  force     the bowl: pull to the center, push against what is rising, tanh-bounded; past the 0.95 wall: fail up
  write     up wire: the ceiling moves by the force (fast up, gently down), inside its cover: from the card's own busy
            clock (never slower than native while there is work) to the top; down wire: the lid at the card's own busy
            draw plus --lid-headroom, never under it and never over the start limit, inside the declared envelope;
            fail up: ceiling to the top and the lid to the start limit at once
  guards    blind (meters unreadable, response times stale): fail up; heat (the card reports a thermal or hardware
            slowdown): never tighten; one writer: a power limit neither mine nor the start means another writer, so
            observe only from then on and exit 5; read-back: every write is read back
  restore   on exit, kill file or SIGTERM: clocks reset (-rgc) and the power limit back to the start, read back

The audit (--audit) carries the same records the bench reads from the one-wire governor (snapshot, decision with
telemetry and decided_by, write and actuator for each power-limit write, restored), plus clock_write records.
Exit: 0 clean, 3 restore failed, 4 a write refused, 5 another writer.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import signal
import subprocess
import sys
import time

from omnicompass.bowl import Band, Bowl, clamp
from omni_controller.gpu_governor import query, snapshot, throttle, slowed, WriteFailed, SNAPSHOT
from omni_controller.muscles import latency_sense


def smi_run(smi, args):
    try:
        p = subprocess.run(shlex.split(smi) + args, capture_output=True, text=True, timeout=20)
        return p.returncode, p.stderr.strip()[:300]
    except (subprocess.SubprocessError, OSError) as e:
        return -1, f"{type(e).__name__}: {e}"[:300]


def query_top_clock(smi, g):
    try:
        out = subprocess.run(shlex.split(smi) + ["-i", str(g), "--query-gpu=clocks.max.sm", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, check=True).stdout
        return float(out.strip().splitlines()[0])
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        return None


def query_min_clock(smi, g):
    """The lowest graphics clock the card supports (the floor of a -lgc range); 300 MHz if the driver will not list them."""
    try:
        out = subprocess.run(shlex.split(smi) + ["-i", str(g), "--query-supported-clocks=graphics", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, check=True).stdout
        return int(min(float(x) for x in out.split() if x.strip()))
    except (subprocess.SubprocessError, OSError, ValueError):
        return 300


class GpuBowl:
    def __init__(self, a):
        self.a = a
        self.g = int(str(a.gpus).split(",")[0])
        self.log = open(a.audit, "a")
        self.writes = 0
        self.foreign = False
        self.clock_set = False
        self.enforced_ok = query(a.smi, [self.g], enforced=True) is not None
        s = query(a.smi, [self.g], self.enforced_ok)
        if s is None:
            raise SystemExit("nvidia-smi unreadable at start: no snapshot, so I take no authority")
        snap = snapshot(a.smi, [self.g])
        self.start = s[self.g]["limit"]
        self.expect = self.start
        self.top = query_top_clock(a.smi, self.g) or s[self.g]["clock_mhz"]
        self.floor_w = max(float(a.floor_w or 0.0), s[self.g]["min"])
        self.c_lo = a.clock_min_share * self.top
        self.c_floor = query_min_clock(a.smi, self.g)
        self.ceiling = self.top            # where the bowl holds the ceiling (continuous)
        self.written_ceiling = self.top    # what the card was last told
        self.busy_clk, self.busy_draw = [], []    # the card on its own: busy clock and busy draw, ceiling at the top
        self.brain = Bowl(Band(0.0, 1.0), dt=a.interval, tau=2.0 * a.interval, kp=1.0, smooth=0.3)
        self.brain.kd *= 3.0
        self.audit({"snapshot": {str(self.g): {"limit_w": self.start, "min_limit_w": s[self.g]["min"],
                                               "enforced_w": s[self.g]["enforced"] if self.enforced_ok else None,
                                               "clock_top_mhz": self.top,
                                               **{f: snap[f][str(self.g)] for f in SNAPSHOT}}},
                    "engine": "bowl, two wires", "mode": a.mode,
                    "covers": {"clock_mhz": [round(self.c_lo), round(self.top)], "power_w": [self.floor_w, self.start]}})
        if a.mode == "cap" and snap["power.management"][str(self.g)].lower() != "enabled":
            self.audit({"refused": "power management not Enabled: a written limit would not bind"})
            raise SystemExit("power management not Enabled: cap mode refused, no authority taken")

    def audit(self, rec):
        self.log.write(json.dumps({"time": time.time(), **rec}) + "\n"); self.log.flush()

    def position(self, util):
        a = self.a
        ls = latency_sense(a.latency_file, a.latency_window_s) if a.latency_file and a.slo_ms else None
        if ls is not None and ls["blind"]:
            return None, ls
        resp = 0.0
        if ls is not None:
            bare = a.slo_ms / 10.0
            resp = (ls["p95"] - bare) / (a.slo_ms - bare)
            if ls["fail"]:
                resp = max(resp, 1.0)
        return resp, ls

    def learn(self, r):
        """The card on its own: while the ceiling is at the top and the card is busy, its clock and draw are native's."""
        if r is not None and self.written_ceiling >= self.top and r["limit"] >= self.start - 1.0 and r["util"] >= 0.9:
            self.busy_clk = (self.busy_clk + [r["clock_mhz"]])[-200:]
            self.busy_draw = (self.busy_draw + [r["draw"]])[-200:]

    def native(self):
        """(busy clock, busy draw) of the card on its own, or (None, None) until enough busy readings are in."""
        if len(self.busy_clk) < self.a.learn_samples:
            return None, None
        c, d = sorted(self.busy_clk), sorted(self.busy_draw)
        return c[len(c) // 2], d[int(0.9 * (len(d) - 1))]

    def write_clock(self, mhz, why):
        mhz = int(round(mhz))
        cmd = ["-i", str(self.g), "-lgc", f"{self.c_floor},{mhz}"]
        if self.a.mode != "cap" or self.foreign:
            self.audit({"would_clock_write": cmd, "why": why}); return
        rc, err = smi_run(self.a.smi, cmd)
        self.audit({"clock_write": cmd, "why": why, "rc": rc, "stderr": err})
        if rc != 0:
            raise WriteFailed(f"nvidia-smi -lgc {self.c_floor},{mhz} returned {rc}: {err}")
        self.clock_set = True
        self.writes += 1

    def write_limit(self, w, why):
        w = int(w)
        cmd = ["nvidia-smi", "-i", str(self.g), "-pl", str(w)]
        if self.a.mode != "cap" or self.foreign:
            self.audit({"would_write": cmd, "why": why}); return
        self.audit({"write": cmd, "why": why})
        t0 = time.time()
        rc, err = smi_run(self.a.smi, ["-i", str(self.g), "-pl", str(w)])
        act = {"gpu": self.g, "requested_w": w, "t_requested": t0, "rc": rc, "stderr": err}
        if rc != 0:
            self.audit({"actuator": act, "write_failed": cmd})
            raise WriteFailed(f"nvidia-smi -pl {w} returned {rc}: {err}")
        self.writes += 1
        s = query(self.a.smi, [self.g], self.enforced_ok)
        if s is not None:
            back = s[self.g]
            act.update({"readback_w": back["limit"], "enforced_w": back["enforced"], "t_readback": time.time(),
                        "realized": abs(back["limit"] - w) < 1.0, "override": back["enforced"] < back["limit"] - 1.0})
            if act["realized"]:
                act["delay_s"] = round(act["t_readback"] - t0, 3)
                self.expect = w
        self.audit({"actuator": act})

    def step(self):
        a, g = self.a, self.g
        s = query(a.smi, [g], self.enforced_ok)
        if s is None:
            p, ls, r = None, None, None
        else:
            r = s[g]
            if abs(r["limit"] - self.expect) >= 1.0 and not self.foreign:
                self.foreign = True
                self.audit({"foreign_writer": {"gpu": g, "reads_w": r["limit"], "expected_w": self.expect},
                            "action": "observe only from now on; both wires left to the other writer"})
            p, ls = self.position(r["util"])
        self.learn(r)
        n_clk, n_draw = self.native()
        thr = throttle(a.smi, [g]) if r is not None else None
        heat = slowed((thr or {}).get(g))
        saturated = r is not None and r["util"] >= a.race_util
        if p is None or p >= self.brain.band.wall_high or saturated:
            # fail up past the wall or blind; and race while work waits (the card saturated: a queue is forming), so a
            # burst is always served at full speed and the bowl paces only the slack between bursts
            if p is not None:
                self.brain.force(p)
            ceiling, lid = self.top, self.start
            who = "blind_fail_up" if p is None else "fail_up" if p >= self.brain.band.wall_high else "race"
        else:
            F = self.brain.force(p)
            # the speed floor: never under the clock the card reaches on its own while busy (until that is learned,
            # the top), so work waiting on the card is never served slower than native
            c_floor = self.top if n_clk is None else max(self.c_lo, min(self.top, n_clk))
            gain = (a.up_gain if F > 0 else a.down_gain) * (self.top - c_floor)
            ceiling = clamp(self.ceiling + gain * F, c_floor, self.top)
            if heat and ceiling < self.ceiling:
                ceiling, who = self.ceiling, "thermal_hold"
            else:
                who = "bowl"
            # the lid: the start limit scaled to what a fully busy card draws at this ceiling (a fifth of the draw does not
            # scale with the clock; the rest goes as clock^2.5, clock times voltage squared), plus headroom; at the top
            # clock the lid is the start limit, so the lid never adds a hammer of its own
            # the lid: never under what the card draws on its own while busy (its own meter, not a curve), plus
            # headroom; the start limit until that is learned
            lid = self.start if n_draw is None else clamp(math.ceil(n_draw * (1.0 + a.lid_headroom)), self.floor_w, self.start)
        rec = {"decision": {str(g): {"telemetry": None if r is None else {
                   "util": r["util"], "draw_w": r["draw"], "temp_c": r["temp"], "limit_w": r["limit"],
                   "enforced_w": r["enforced"], "clock_mhz": r["clock_mhz"], "throttle": (thr or {}).get(g)},
               "position": None if p is None else round(p, 4), "velocity": round(self.brain.v, 4),
               "latency_p95_ms": None if not ls else ls.get("p95"),
               "ceiling_mhz": round(ceiling), "want_w": int(lid), "decided_by": who,
               "native_busy_clock_mhz": n_clk, "native_busy_draw_w": n_draw}}}
        self.audit(rec)
        self.ceiling = ceiling
        if abs(ceiling - self.written_ceiling) >= a.min_change_mhz or (ceiling >= self.top and self.written_ceiling < self.top):
            if ceiling >= self.top and self.clock_set and a.mode == "cap" and not self.foreign:
                rc, err = smi_run(a.smi, ["-i", str(g), "-rgc"])
                self.audit({"clock_write": ["-i", str(g), "-rgc"], "why": who, "rc": rc, "stderr": err})
                if rc != 0:
                    raise WriteFailed(f"nvidia-smi -rgc returned {rc}: {err}")
                self.clock_set = False
            elif ceiling < self.top:
                self.write_clock(ceiling, who)
            self.written_ceiling = ceiling
        cur = r["limit"] if r is not None else self.expect
        if abs(lid - cur) >= a.min_change_w or (lid == self.start and cur != lid):
            self.write_limit(lid, who)

    def restore(self):
        failed = []
        if self.a.mode == "cap" and not self.foreign:
            rc, err = smi_run(self.a.smi, ["-i", str(self.g), "-rgc"])
            self.audit({"clock_write": ["-i", str(self.g), "-rgc"], "why": "restore", "rc": rc, "stderr": err})
            if rc != 0:
                failed.append(f"-rgc returned {rc}: {err}")
            s = query(self.a.smi, [self.g], self.enforced_ok)
            if s is None or abs(s[self.g]["limit"] - self.start) >= 1.0:
                try:
                    self.write_limit(self.start, "kill switch: the limit read at start")
                except WriteFailed as e:
                    failed.append(str(e))
        s = query(self.a.smi, [self.g], self.enforced_ok) or {}
        back = s[self.g]["limit"] if self.g in s else None
        ok = self.foreign or (not failed and back is not None and abs(back - self.start) < 1.0)
        self.audit({"restored": {str(self.g): back}, "start": {str(self.g): self.start}, "ok": ok,
                    "writes": self.writes, "foreign_writer": self.foreign, "restore_write_failed": failed})
        return ok


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["watch", "cap"], default="watch")
    ap.add_argument("--gpus", default="0")
    ap.add_argument("--smi", default=os.environ.get("NVIDIA_SMI", "nvidia-smi"))
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--duration", type=float, default=0.0)
    ap.add_argument("--audit", default="gpu_bowl_audit.jsonl")
    ap.add_argument("--kill-file", default="/tmp/omni-gpu-kill")
    ap.add_argument("--latency-file", default="")
    ap.add_argument("--slo-ms", type=float, default=0.0)
    ap.add_argument("--latency-window-s", type=float, default=5.0, help="seconds of response times the position reads")
    ap.add_argument("--race-util", type=float, default=0.95, help="utilization at which work is waiting: race, never pace")
    ap.add_argument("--learn-samples", type=int, default=15, help="busy readings of the card on its own before the bowl may lower anything")
    ap.add_argument("--floor-w", type=float, default=0.0, help="the declared envelope's lowest watts")
    ap.add_argument("--clock-min-share", type=float, default=0.35, help="the clock ceiling's cover: lowest share of the top")
    ap.add_argument("--up-gain", type=float, default=0.10, help="share of the clock cover moved per unit of force, up")
    ap.add_argument("--down-gain", type=float, default=0.02, help="share of the clock cover moved per unit of force, down")
    ap.add_argument("--lid-headroom", type=float, default=0.10, help="the lid above the draw the ceiling takes")
    ap.add_argument("--min-change-mhz", type=float, default=15.0)
    ap.add_argument("--min-change-w", type=float, default=3.0)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    gov = GpuBowl(a)
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("now", True))
    t0 = time.time()
    failed = False
    try:
        while not stop["now"] and not os.path.exists(a.kill_file) and (a.duration <= 0 or time.time() - t0 < a.duration):
            try:
                gov.step()
            except WriteFailed as e:
                gov.audit({"fatal": f"write failed: {e}"}); failed = True
                break
            except Exception as e:  # noqa: BLE001  a failed decision is logged; the kill path still runs
                gov.audit({"error": f"{type(e).__name__}: {e}"})
            end = time.time() + a.interval
            while time.time() < end and not stop["now"] and not os.path.exists(a.kill_file):
                time.sleep(0.2)
    finally:
        ok = gov.restore()
    return 5 if gov.foreign else 3 if not ok else 4 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
