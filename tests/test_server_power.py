# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Whole-server watts from the server's own management controller (tools/wall_meter.py): a stand-in Redfish controller
(newer EnvironmentMetrics, and the older Power resource) and a stand-in ipmitool each give the reading the bench
records; the reader only ever sends GET requests."""
import http.server, json, os, stat, sys, tempfile, threading
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import tools.wall_meter as W

SEEN = []


def serve(newer):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            SEEN.append((self.command, self.path, self.headers.get("Authorization")))
            body = {"/redfish/v1/Chassis": {"Members": [{"@odata.id": "/redfish/v1/Chassis/1"}]},
                    "/redfish/v1/Chassis/1/Power": {"PowerControl": [{"PowerConsumedWatts": 2875.0}]}}
            if newer:
                body["/redfish/v1/Chassis/1/EnvironmentMetrics"] = {"PowerWatts": {"Reading": 3120.5}}
            if self.path not in body:
                self.send_response(404); self.end_headers(); return
            b = json.dumps(body[self.path]).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

        def log_message(self, *a):
            pass
    s = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def main():
    os.environ.update(REDFISH_USER="ro", REDFISH_PASSWORD="x")
    for newer, want in ((True, 3120.5), (False, 2875.0)):
        s = serve(newer)
        got = W.read(f"redfish:http://127.0.0.1:{s.server_port}")
        assert got == want, (newer, got)
        s.shutdown()
    assert {m for m, _, _ in SEEN} == {"GET"} and all(a and a.startswith("Basic ") for _, _, a in SEEN)
    d = Path(tempfile.mkdtemp()); f = d / "ipmitool"
    f.write_text("#!/bin/sh\necho '    Instantaneous power reading:                  1840 Watts'\n")
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    os.environ["PATH"] = f"{d}:{os.environ['PATH']}"
    assert W.read("ipmi:local") == 1840.0
    print("PASS server power: Redfish (EnvironmentMetrics and the older Power resource) and IPMI DCMI give the "
          "whole-server watts; the reader only sends GET requests")


if __name__ == "__main__":
    main()
