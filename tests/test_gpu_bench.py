"""The GPU bench (scripts/gpu_paired.sh, omni_controller/gpu_governor.py, tools/gpu_reps.py) against a stand-in nvidia-smi
(tests/fake_gpu/nvidia-smi): the governor's contract and the bench's validity checks, without a GPU.

Governor contract: the start limit is read and recorded before any write; watch computes and records but executes no
write; a written limit is never below draw x 1.3 nor the device minimum, never above the start limit; no second write
until the last one reads back; a blind sense returns the start limit; a response-time breach returns the start limit;
the kill switch restores the start limit and reads it back.
Bench: one command runs native / watch / omni with rotated order and prints the table; a watch arm that writes, or an
arm that ends away from the start limit, makes the run INVALID."""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
SMI = str(ROOT / "tests" / "fake_gpu" / "nvidia-smi")


def state(d, **kw):
    s = {"limit": {"0": 300.0}, "default": 300, "min": 100, "max": 350, "draw_w": 180.0, "util": 40, "temp": 60}
    s.update(kw); p = d / "state.json"; p.write_text(json.dumps(s)); os.environ["FAKE_SMI_STATE"] = str(p)
    if Path(str(p) + ".writes").exists():
        Path(str(p) + ".writes").unlink()
    return p


def args(d, mode, **kw):
    a = dict(mode=mode, gpus="0", smi=SMI, interval=1.0, duration=0.0, audit=str(d / f"audit-{mode}.jsonl"),
             kill_file=str(d / "kill"), headroom=0.3, min_change_w=5.0, temp_limit=83.0, latency_file="", slo_ms=0.0,
             latency_window_s=30.0, slo_clear=1)
    a.update(kw); return SimpleNamespace(**a)


def recs(path):
    return [json.loads(x) for x in open(path)]


def governor():
    from omni_controller.gpu_governor import GpuGovernor
    d = Path(tempfile.mkdtemp())
    p = state(d)
    # watch: decides, records, never executes
    g = GpuGovernor(args(d, "watch"))
    for _ in range(6):
        g.step()
    r = recs(d / "audit-watch.jsonl")
    assert r[0]["snapshot"]["0"]["limit_w"] == 300.0
    assert not any("write" in x for x in r) and any("would_write" in x for x in r), r
    assert json.load(open(p))["limit"]["0"] == 300.0 and not Path(str(p) + ".writes").exists()
    assert g.restore()
    # cap: writes within the shield, reads back, kill restores
    p = state(d)
    g = GpuGovernor(args(d, "cap"))
    for _ in range(6):
        g.step()
    w = [x for x in recs(d / "audit-cap.jsonl") if "write" in x]
    assert w, "the governor wrote no limit at 40% utilisation"
    for x in w:
        watts = int(x["write"][-1])
        assert max(100, 180 * 1.3) <= watts <= 300, watts
    assert json.load(open(p))["limit"]["0"] == 234.0            # draw 180 W x 1.3: the floor holds
    # read-back: a limit that did not land blocks the next write
    g.written[0] = 200; g.step()
    last = recs(d / "audit-cap.jsonl")[-1]
    assert last["decision"]["0"]["hold"] == "last write not read back", last
    g.written.pop(0)
    # blind: the start limit at once
    os.environ["FAKE_SMI_BLIND"] = "1"
    try:
        g.cap[0] = 0.78; g.step()
    finally:
        del os.environ["FAKE_SMI_BLIND"]
    assert json.load(open(p))["limit"]["0"] == 300.0, "blind sense did not return the start limit"
    # response-time breach: the start limit
    p = state(d)
    lat = d / "lat.csv"
    lat.write_text("elapsed_seconds,latency_ms,ok\n1,10,1\n2,10,1\n")
    g = GpuGovernor(args(d, "cap", audit=str(d / "audit-slo.jsonl"), latency_file=str(lat), slo_ms=100.0))
    g.step(); assert json.load(open(p))["limit"]["0"] == 234.0
    lat.write_text("elapsed_seconds,latency_ms,ok\n1,10,1\n2,500,1\n3,500,1\n"); g.step()
    assert json.load(open(p))["limit"]["0"] == 300.0, "a response-time breach did not return the start limit"
    # kill switch after a cap
    lat.write_text("elapsed_seconds,latency_ms,ok\n1,10,1\n2,10,1\n"); g.lp_hist = []
    g.step(); assert json.load(open(p))["limit"]["0"] == 234.0
    assert g.restore() and json.load(open(p))["limit"]["0"] == 300.0
    assert recs(d / "audit-slo.jsonl")[-1]["ok"] is True


def bench():
    d = Path(tempfile.mkdtemp())
    state(d)
    env = dict(os.environ, NVIDIA_SMI=SMI, SIM="1", REPS="2", DURATION="5", DRAIN="1", COOLDOWN="0", INTERVAL="1",
               SAMPLE_MS="200", OUT=str(d / "run"), WORKLOAD_ARGS="--calib 5 --target-ms 20", WALL_METER="cmd:echo 250")
    r = subprocess.run(["bash", str(ROOT / "scripts" / "gpu_paired.sh")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    out = json.loads((d / "run" / "GPU_REPS.json").read_text())
    assert not out["problems"], out["problems"]
    assert {c["writes"] for c in out["checks"]["watch"].values()} == {0}
    assert all(c["writes"] > 0 for c in out["checks"]["omni"].values())
    assert "energy, GPU (J)" in out["paired"]["omni"] and (d / "run" / "SHA256SUMS.txt").exists()
    assert "work per energy (served requests per kJ)" in out["paired"]["omni"] and out["freeze"]["phase"] == "smoke"
    assert "energy, whole machine at the wall (J)" in out["paired"]["omni"] and out["headline"]["wall"], "wall meter not integrated"
    assert out["headline"]["valid"] and out["headline"]["verdict"] and "Verdict on the preregistered question" in (d / "run" / "GPU_REPS.md").read_text()
    # every Omni decision records the whole chain
    dec = [json.loads(x) for x in open(d / "run" / "rep-1" / "omni" / "audit.jsonl") if '"decision"' in x]
    chain = [v for r in dec for v in r["decision"].values() if "telemetry" in v]
    assert chain and all(k in chain[-1] for k in ("state_observed", "state_projected_next", "prediction_error", "admissible",
                                                  "requested_cap", "granted_cap", "shield_bound", "want_w")), chain[-1]
    # Omni's code changing mid-run invalidates it
    fz = json.loads((d / "run" / "FREEZE_END.json").read_text()); fz["files"]["omni_controller/gpu_governor.py"] = "0" * 64
    (d / "run" / "FREEZE_END.json").write_text(json.dumps(fz))
    from tools.gpu_reps import main as reps0
    assert reps0(str(d / "run")) == 2
    (d / "run" / "FREEZE_END.json").write_text((d / "run" / "FREEZE.json").read_text())
    # rotated order: rep 1 starts native, rep 2 starts watch
    t = lambda rep, a: float((d / "run" / f"rep-{rep}" / a / "window_start.txt").read_text())
    assert t(1, "native") < t(1, "watch") < t(1, "omni") and t(2, "watch") < t(2, "omni") < t(2, "native")
    # a watch arm that wrote makes the run invalid
    with open(d / "run" / "rep-1" / "watch" / "audit.jsonl", "a") as f:
        f.write(json.dumps({"write": ["nvidia-smi", "-i", "0", "-pl", "250"]}) + "\n")
    from tools.gpu_reps import main as reps
    assert reps(str(d / "run")) == 2


def pooled():
    """Repetitions spread over machines (REP_ONLY): each machine's run carries its own records; pooled, they make one
    valid table."""
    import shutil
    d = Path(tempfile.mkdtemp()); state(d)
    for k in (1, 2):
        env = dict(os.environ, NVIDIA_SMI=SMI, SIM="1", REP_ONLY=str(k), DURATION="4", DRAIN="1", COOLDOWN="0", INTERVAL="1",
                   SAMPLE_MS="200", OUT=str(d / f"m{k}"), WORKLOAD_ARGS="--calib 5 --target-ms 20")
        r = subprocess.run(["bash", str(ROOT / "scripts" / "gpu_paired.sh")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
        shutil.copytree(d / f"m{k}" / f"rep-{k}", d / "pool" / f"rep-{k}")
    from tools.gpu_reps import main as reps
    assert reps(str(d / "pool")) == 0
    out = json.loads((d / "pool" / "GPU_REPS.json").read_text())
    assert sorted(out["checks"]["omni"]) == ["1", "2"] and not out["problems"]


def plugs():
    """The smart-plug readers against a stand-in plug on this machine: Shelly Gen1, Shelly Gen2/3, Tasmota."""
    import http.server, threading
    from tools.wall_meter import read
    body = {"/meter/0": {"power": 101.5}, "/rpc/Switch.GetStatus?id=0": {"apower": 202.5},
            "/cm?cmnd=Status%208": {"StatusSNS": {"ENERGY": {"Power": 303}}}}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            b = json.dumps(body[self.path]).encode(); self.send_response(200); self.end_headers(); self.wfile.write(b)

        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    ip = f"127.0.0.1:{srv.server_port}"
    assert (read(f"shelly1:{ip}"), read(f"shelly2:{ip}"), read(f"tasmota:{ip}"), read("cmd:echo 44")) == (101.5, 202.5, 303.0, 44.0)
    srv.shutdown()


def guards():
    """The slowdown bounds: the limit never under --min-share of the start limit, and a busy card (smoothed utilization
    at or over --util-gate) gets the start limit back, the cap resuming only under the gate less --util-band."""
    from omni_controller.gpu_governor import GpuGovernor, parser as gp
    d = Path(tempfile.mkdtemp())
    p = state(d, draw_w=60.0, util=20)
    g = GpuGovernor(args(d, "cap", min_share=0.75, util_gate=0.5, util_band=0.1))
    for _ in range(6):
        g.step()
    assert json.load(open(p))["limit"]["0"] == 225.0, "share floor: 0.75 x 300 W, not 60 W x 1.3"
    last = [x for x in recs(d / "audit-cap.jsonl") if "decision" in x][-1]["decision"]["0"]
    assert last["shield_bound"] == "share_floor", last
    s = json.load(open(p)); s["util"] = 90; json.dump(s, open(p, "w"))
    g.step()                                              # smoothed 0.2 -> 0.55: over the gate
    assert json.load(open(p))["limit"]["0"] == 300.0, "busy: the start limit at once"
    s = json.load(open(p)); s["util"] = 40; json.dump(s, open(p, "w"))
    g.step()                                              # smoothed 0.475: under the gate, inside the band: held
    assert json.load(open(p))["limit"]["0"] == 300.0, "inside the band: still the start limit"
    s = json.load(open(p)); s["util"] = 10; json.dump(s, open(p, "w"))
    g.step()                                              # 0.29: under 0.4, the cap returns
    assert json.load(open(p))["limit"]["0"] == 225.0, "calm: the cap returns"
    a = gp().parse_args([])
    assert (a.min_share, a.util_gate, a.util_band, a.interval) == (0.70, 0.5, 0.1, 2.0), "the command line's defaults"
    assert g.restore() and json.load(open(p))["limit"]["0"] == 300.0


def main():
    plugs(); governor(); guards(); bench(); pooled()
    print("PASS  GPU bench: governor contract (watch writes nothing, shield floor, share floor, busy gate, read-back, blind, SLO reflex, kill) "
          "and the one-command paired run with its validity checks")


if __name__ == "__main__":
    main()
