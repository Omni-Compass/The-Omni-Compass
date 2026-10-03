# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The controller's reads through one kubectl proxy (omni_controller/controller.py, Kube): against a stand-in API
server, every read the controller and its muscles make comes back in the shape kubectl prints, a missing object is an
error as it is from kubectl, and a read the proxy path does not translate goes to kubectl."""
import json, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.controller import Kube

SEEN = []
OBJ = {
    "/api/v1/nodes": {"items": [{"metadata": {"name": "n0"}}, {"metadata": {"name": "n1"}}]},
    "/api/v1/pods": {"items": [{"metadata": {"name": "p0"}}]},
    "/api/v1/namespaces/default/pods": {"items": [{"metadata": {"name": "web-1"}}]},
    "/apis/autoscaling/v2/horizontalpodautoscalers": {"items": [{"metadata": {"name": "web"}}]},
    "/apis/apps/v1/namespaces/default/deployments/php-apache": {"metadata": {"name": "php-apache"}, "spec": {}},
    "/api/v1/namespaces/default/configmaps/omni-security": {"data": {"block": "0"}},
    "/apis/batch/v1/jobs": {"items": []},
    "/apis/metrics.k8s.io/v1beta1/nodes": {"items": [{"metadata": {"name": "n0"}, "usage": {"cpu": "250000000n"}},
                                                     {"metadata": {"name": "n1"}, "usage": {"cpu": "1"}}]},
    "/apis/metrics.k8s.io/v1beta1/namespaces/default/pods": {"items": [{"metadata": {"name": "web-1"},
                                                                        "containers": [{"usage": {"cpu": "120m"}}]}]},
}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        SEEN.append(self.path)
        path = self.path.split("?")[0]
        if path not in OBJ:
            self.send_response(404); self.end_headers(); return
        b = json.dumps(OBJ[path]).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass


def main():
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    k = Kube("kubectl-not-used", proxy=False)
    k.base = f"http://127.0.0.1:{srv.server_port}"
    assert [n["metadata"]["name"] for n in k.get("get", "nodes", "-o", "json")["items"]] == ["n0", "n1"]
    assert k.get("get", "pods", "-A", "-o", "json")["items"][0]["metadata"]["name"] == "p0"
    assert k.get("get", "hpa", "-A", "-o", "json")["items"][0]["metadata"]["name"] == "web"
    assert k.get("get", "deployment", "php-apache", "-n", "default", "-o", "json")["metadata"]["name"] == "php-apache"
    assert k.get("get", "configmap", "omni-security", "-n", "default", "-o", "json")["data"]["block"] == "0"
    assert k.get("get", "jobs", "-A", "-l", "omnicompass.io/pausable=true", "-o", "json")["items"] == []
    assert any("labelSelector=omnicompass.io%2Fpausable%3Dtrue" in p for p in SEEN)
    top = k.get("top", "nodes", "--no-headers").split("\n")
    assert top[0].split()[:2] == ["n0", "250m"] and top[1].split()[:2] == ["n1", "1000m"], top
    assert k.get("top", "pods", "-n", "default", "-l", "run=php-apache", "--no-headers").split()[:2] == ["web-1", "120m"]
    names = k.get("get", "pods", "-A", "--field-selector=status.phase=Pending", "-o", "name")
    assert names == "pod/p0\n" and any("fieldSelector=status.phase%3DPending" in p for p in SEEN)
    try:
        k.get("get", "deployment", "missing", "-n", "default", "-o", "json"); raise AssertionError("404 must be an error")
    except subprocess.CalledProcessError:
        pass
    assert k._rest(["get", "pods", "-A", "-o", "wide"]) is None          # not translated: kubectl answers it
    assert k._rest(["rollout", "status", "deployment/x"]) is None
    srv.shutdown()
    print("PASS controller reads through one kubectl proxy: every read in kubectl's own shape, missing objects are errors, "
          "anything else goes to kubectl")


if __name__ == "__main__":
    main()
