# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Whole-machine watts from the wall, read from a smart plug that Omni-Compass never reads or writes.

The plug sits between the wall socket and the machine under test. Its reading covers everything the machine draws:
GPU, CPU, memory, fans, power-supply losses. It is the measurement a buyer understands at once, and it is independent
of Omni by construction: the governor is never given the plug's address.

SPEC
  shelly1:<ip>      Shelly Gen1 plug (Plug S, Plug US):  http://<ip>/meter/0            -> "power"
  shelly2:<ip>      Shelly Gen2/Gen3 plug (Plus Plug):   http://<ip>/rpc/Switch.GetStatus?id=0 -> "apower"
  tasmota:<ip>      any plug flashed with Tasmota:       http://<ip>/cm?cmnd=Status%208 -> StatusSNS.ENERGY.Power
  cmd:<command>     any shell command that prints watts (a USB meter, a PDU script, IPMI, a lab instrument)
Usage
  python tools/wall_meter.py SPEC --once              print one reading (check the plug before a run)
  python tools/wall_meter.py SPEC OUT.csv [--interval 1]   write epoch_s,watts until stopped
"""
from __future__ import annotations

import argparse, json, shlex, signal, subprocess, sys, time, urllib.request


def read(spec, timeout=3.0):
    kind, _, where = spec.partition(":")
    if kind == "cmd":
        out = subprocess.run(where, shell=True, capture_output=True, text=True, timeout=timeout + 5).stdout
        return float(out.split()[0])
    url = {"shelly1": f"http://{where}/meter/0", "shelly2": f"http://{where}/rpc/Switch.GetStatus?id=0",
           "tasmota": f"http://{where}/cm?cmnd=Status%208"}[kind]
    # a plug on the home network: never through a proxy
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    d = json.loads(opener.open(url, timeout=timeout).read())
    if kind == "shelly1":
        return float(d["power"])
    if kind == "shelly2":
        return float(d["apower"])
    return float(d["StatusSNS"]["ENERGY"]["Power"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=1.0)
    a = ap.parse_args(argv)
    if a.once or not a.out:
        print(f"{read(a.spec):.2f}")
        return 0
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("now", True))
    with open(a.out, "w") as f:
        f.write("epoch_s,watts\n"); f.flush()
        while not stop["now"]:
            t = time.time()
            try:
                f.write(f"{t:.3f},{read(a.spec):.3f}\n")
            except Exception as e:  # noqa: BLE001  a missed reading is a gap, recorded as such, never a guess
                f.write(f"{t:.3f},\n")
                print(f"wall meter: {type(e).__name__}: {e}", file=sys.stderr)
            f.flush()
            time.sleep(max(0.0, a.interval - (time.time() - t)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
