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
      OFF or ON, and every governor running

OMNI_MASTER_OFF sets the switch file (default /tmp/omni-compass/OFF); every governor and this tool must agree on it.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omnicompass import master  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["off", "on", "status"])
    ap.add_argument("--reason", default="turned off by hand")
    ap.add_argument("--wait", type=float, default=60.0)
    a = ap.parse_args(argv)
    p = master.switch_path()
    if a.cmd == "status":
        print(f"master switch: {'OFF' if master.is_off() else 'ON'} ({p})")
        for r in master.running():
            print(f"  running: {r['name']} pid {r['pid']}")
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
    if not left:
        print("every governor has restored and exited")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
