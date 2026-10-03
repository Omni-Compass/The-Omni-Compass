# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The master switch: one OFF for the whole harness, not one muscle at a time.

Every Omni-Compass governor on a machine (the Kubernetes controller, the GPU governors, any muscle they drive) obeys one
switch, in a human hand:

  OFF   the switch file exists (OMNI_MASTER_OFF, by default /tmp/omni-compass/OFF). Every running governor sees it at its
        next decision, puts every setting it ever wrote back to the value it read before its first write, reads each one
        back, writes its last audit line and exits. No governor starts while the switch is OFF.
  ON    the switch file is removed. Nothing restarts by itself: a governor runs again only when someone starts it.

The switch is also pulled from the command line, which signals every registered governor at once so none waits for its
next decision:

  python3 tools/omni_switch.py off [--reason TEXT]    turn the whole harness off, wait for every governor to restore
  python3 tools/omni_switch.py on                      allow governors to be started again
  python3 tools/omni_switch.py status                  OFF or ON, and every governor running

A governor that cannot read the switch (a filesystem it cannot reach) treats that as OFF: when in doubt, hand back.
"""
from __future__ import annotations

import atexit
import json
import os
import time

DEFAULT_DIR = "/tmp/omni-compass"


def switch_path() -> str:
    return os.environ.get("OMNI_MASTER_OFF", os.path.join(DEFAULT_DIR, "OFF"))


def registry_dir() -> str:
    return os.environ.get("OMNI_REGISTRY", os.path.join(os.path.dirname(switch_path()) or DEFAULT_DIR, "running"))


def is_off() -> bool:
    """True when the master switch is OFF (or cannot be read: when in doubt, hand back)."""
    p = switch_path()
    try:
        return os.path.exists(p)
    except OSError:
        return True


def reason() -> str:
    try:
        return json.loads(open(switch_path()).read()).get("reason", "")
    except (OSError, ValueError):
        return ""


def register(name: str) -> str:
    """Record this governor as running, so the switch can signal it; removed when the process exits."""
    d = registry_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{os.getpid()}.json")
    with open(path, "w") as f:
        json.dump({"pid": os.getpid(), "name": name, "started": time.time()}, f)

    def _gone():
        try:
            os.remove(path)
        except OSError:
            pass
    atexit.register(_gone)
    return path


def running():
    """Every governor registered as running whose process is alive."""
    out = []
    d = registry_dir()
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        p = os.path.join(d, fn)
        try:
            rec = json.loads(open(p).read())
            os.kill(int(rec["pid"]), 0)
            out.append(rec)
        except (OSError, ValueError, KeyError):
            try:
                os.remove(p)                       # a record left by a process that no longer exists
            except OSError:
                pass
    return out


def refuse_if_off(name: str):
    """Called by every governor at start: no authority is taken while the master switch is OFF."""
    if is_off():
        raise SystemExit(f"{name}: the Omni-Compass master switch is OFF ({switch_path()}"
                         f"{': ' + reason() if reason() else ''}); nothing started. Turn it on with: "
                         "python3 tools/omni_switch.py on")
