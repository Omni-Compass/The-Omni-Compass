#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The master switch for the whole Omni-Compass harness (omnicompass/master.py).

  python3 tools/omni_switch.py off [--reason TEXT] [--wait 60]
      turns every Omni-Compass governor on this machine off at once: sets the switch, signals every running governor
      (SIGTERM), and waits until each has put every setting back and exited. Exit 0 when all are gone, 1 if any is
      still running after --wait seconds (its name and pid are printed; the switch stays OFF).
  python3 tools/omni_switch.py on
      allows governors to be started again (nothing restarts by itself)
  python3 tools/omni_switch.py status
      OFF or ON, every governor running, and any that died without handing back
  python3 tools/omni_switch.py watchdog [--stale 60] [--every 10] [--once]
      puts back every setting of any governor that died or hung without doing it itself (its recorded restore commands),
      stopping a hung one first; run it as its own service next to the governors

OMNI_MASTER_OFF sets the switch file (default /tmp/omni-compass/OFF); every governor and this tool must agree on it.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omnicompass import master  # noqa: E402


def reclaim(stale):
    """Run the recorded restore commands of every governor that died or hung; returns what was done."""
    done = []
    now = time.time()
    for r in master.records():
        alive = master._alive(r.get("pid", -1))
        limit = stale if stale is not None else r.get("stale_s", 60.0)
        if alive and now - r.get("lease", 0) <= limit:
            continue
        if alive:                                  # hung: stop it before its settings are put back over it
            try:
                os.kill(int(r["pid"]), signal.SIGKILL)
            except OSError:
                pass
        results = []
        for cmd in r.get("restore", []):
            try:
                c = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                results.append({"cmd": cmd, "rc": c.returncode, "stderr": c.stderr[-300:]})
            except (OSError, subprocess.SubprocessError) as e:
                results.append({"cmd": cmd, "rc": None, "error": str(e)})
        ok = all(x.get("rc") == 0 for x in results)
        if ok:
            try:
                os.remove(r["_path"])
            except OSError:
                pass
        done.append({"watchdog": "handed back", "name": r["name"], "pid": r["pid"], "hung": alive, "ok": ok,
                     "commands": results, "time": now})
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["off", "on", "status", "watchdog"])
    ap.add_argument("--stale", type=float, default=None, help="watchdog: a lease older than this many seconds is hung (default: each governor's own)")
    ap.add_argument("--every", type=float, default=10.0, help="watchdog: seconds between passes")
    ap.add_argument("--once", action="store_true", help="watchdog: one pass")
    ap.add_argument("--reason", default="turned off by hand")
    ap.add_argument("--wait", type=float, default=60.0)
    a = ap.parse_args(argv)
    p = master.switch_path()
    if a.cmd == "watchdog":
        while True:
            for r in reclaim(a.stale):
                print(json.dumps(r), flush=True)
            if a.once:
                return 0
            time.sleep(a.every)
    if a.cmd == "status":
        print(f"master switch: {'OFF' if master.is_off() else 'ON'} ({p})")
        for r in master.running():
            print(f"  running: {r['name']} pid {r['pid']}")
        for r in master.orphans():
            print(f"  DIED OR HUNG WITHOUT HANDING BACK: {r['name']} pid {r['pid']} (run: omni_switch.py watchdog --once)")
        return 0
    if a.cmd == "on":
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
        print(f"master switch: ON ({p}); governors may be started again")
        return 0
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w") as f:
        json.dump({"reason": a.reason, "time": time.time()}, f)
    procs = master.running()
    for r in procs:
        try:
            os.kill(int(r["pid"]), signal.SIGTERM)
        except OSError:
            pass
    print(f"master switch: OFF ({p}); signalled {len(procs)} governor(s)")
    t0 = time.time()
    left = procs
    while left and time.time() - t0 < a.wait:
        time.sleep(0.5)
        left = master.running()
    for r in left:
        print(f"  STILL RUNNING after {a.wait:.0f} s: {r['name']} pid {r['pid']}")
    for r in reclaim(None):
        print(f"  handed back for a governor that had died: {r['name']} pid {r['pid']}, ok {r['ok']}")
    if not left:
        print("every governor has restored and exited")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
