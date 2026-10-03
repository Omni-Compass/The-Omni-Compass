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

If a governor dies without handing back (killed outright, the machine crashed, it hung), nothing it wrote may be left
in place. So every governor records, before its first write, the exact commands that put every setting back, and
renews a lease every decision. The watchdog finds any governor whose process is gone or whose lease is older than its
limit and runs those commands for it:

  python3 tools/omni_switch.py watchdog [--stale 60] [--every 10]    keep watching (run it as its own service)
  python3 tools/omni_switch.py watchdog --once                       one pass
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


_ME = {}


def register(name: str, restore=None, stale_s: float = 60.0) -> str:
    """Record this governor as running, so the switch can signal it, with the commands (argument lists) that put every
    setting back if it dies without doing so itself; removed when the process exits cleanly."""
    d = registry_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{os.getpid()}.json")
    rec = {"pid": os.getpid(), "name": name, "started": time.time(), "lease": time.time(), "stale_s": stale_s,
           "restore": restore or []}
    with open(path + ".tmp", "w") as f:
        json.dump(rec, f)
    os.replace(path + ".tmp", path)
    _ME.update(path=path, rec=rec)

    def _gone():
        try:
            os.remove(path)
        except OSError:
            pass
    atexit.register(_gone)
    return path


def heartbeat():
    """Renew this governor's lease (called every decision)."""
    if not _ME:
        return
    _ME["rec"]["lease"] = time.time()
    try:
        with open(_ME["path"] + ".tmp", "w") as f:
            json.dump(_ME["rec"], f)
        os.replace(_ME["path"] + ".tmp", _ME["path"])
    except OSError:
        pass


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def records():
    out = []
    d = registry_dir()
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        try:
            rec = json.loads(open(os.path.join(d, fn)).read())
            rec["_path"] = os.path.join(d, fn)
            out.append(rec)
        except (OSError, ValueError):
            pass
    return out


def orphans(now=None):
    """Governors that are gone without handing back (process dead) or hung (lease older than its limit)."""
    now = now or time.time()
    return [r for r in records() if not _alive(r.get("pid", -1)) or now - r.get("lease", 0) > r.get("stale_s", 60.0)]


def running():
    """Every governor registered as running whose process is alive."""
    return [r for r in records() if _alive(r.get("pid", -1))]


def refuse_if_off(name: str):
    """Called by every governor at start: no authority is taken while the master switch is OFF."""
    if is_off():
        raise SystemExit(f"{name}: the Omni-Compass master switch is OFF ({switch_path()}"
                         f"{': ' + reason() if reason() else ''}); nothing started. Turn it on with: "
                         "python3 tools/omni_switch.py on")
