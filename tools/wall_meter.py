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
  ipmi:local        the server's own management controller, read on the machine: ipmitool dcmi power reading
  ipmi:<host>       the same over the network (IPMI_USER, IPMI_PASSWORD): ipmitool -I lanplus -H <host> ...
  redfish:<host>    the management controller over Redfish (REDFISH_USER, REDFISH_PASSWORD): the first chassis's
                    PowerControl PowerConsumedWatts, or its EnvironmentMetrics PowerWatts on newer controllers. The
                    controller's certificate is checked against REDFISH_CA (a file); REDFISH_INSECURE=1 skips the
                    check for a controller with a self-signed certificate on a private management network
  cmd:<command>     any shell command that prints watts (a USB meter, a PDU script, a lab instrument)
Usage
  python tools/wall_meter.py SPEC --once              print one reading (check the plug before a run)
  python tools/wall_meter.py SPEC OUT.csv [--interval 1]   write epoch_s,watts until stopped
"""
from __future__ import annotations

import argparse, base64, json, os, re, shlex, signal, ssl, subprocess, sys, time, urllib.request


def ipmi(where, timeout):
    """Instantaneous whole-server watts from the management controller (DCMI)."""
    cmd = ["ipmitool"]
    if where != "local":
        cmd += ["-I", "lanplus", "-H", where, "-U", os.environ.get("IPMI_USER", ""), "-E"]   # -E: password from IPMI_PASSWORD
    out = subprocess.run(cmd + ["dcmi", "power", "reading"], capture_output=True, text=True, timeout=timeout + 5,
                         env=dict(os.environ, IPMI_PASSWORD=os.environ.get("IPMI_PASSWORD", ""))).stdout
    m = re.search(r"Instantaneous power reading:\s*([0-9.]+)\s*Watts", out)
    if not m:
        raise ValueError(f"no DCMI power reading in: {out.strip()[:120]!r}")
    return float(m.group(1))


def redfish(where, timeout):
    """Whole-server watts from the management controller over Redfish (read only: GET requests, nothing written)."""
    if os.environ.get("REDFISH_INSECURE") == "1":
        ctx = ssl._create_unverified_context()            # opt-in only: a self-signed controller on a private network
    else:
        ctx = ssl.create_default_context(cafile=os.environ.get("REDFISH_CA") or None)
    auth = base64.b64encode(f"{os.environ.get('REDFISH_USER', '')}:{os.environ.get('REDFISH_PASSWORD', '')}".encode()).decode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))
    base = where if where.startswith("http") else f"https://{where}"

    def get(path):
        req = urllib.request.Request(base + path, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
        return json.loads(opener.open(req, timeout=timeout).read())
    chassis = get("/redfish/v1/Chassis")["Members"][0]["@odata.id"]
    try:
        return float(get(chassis + "/EnvironmentMetrics")["PowerWatts"]["Reading"])
    except Exception:  # noqa: BLE001  older controllers: the Power resource
        return float(get(chassis + "/Power")["PowerControl"][0]["PowerConsumedWatts"])


def read(spec, timeout=3.0):
    kind, _, where = spec.partition(":")
    if kind == "ipmi":
        return ipmi(where, timeout)
    if kind == "redfish":
        return redfish(where, timeout)
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
