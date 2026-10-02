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
               SAMPLE_MS="200", OUT=str(d / "run"), WORKLOAD_ARGS="--calib 5 --target-ms 20", WALL_METER="cmd:echo 250",
               OMNI_ENGINE="one_wire")
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
    # credit per write, against native at the same moments
    assert out["credit"]["by_decider"] and all(r["decided_by"] for r in out["credit"]["writes"])
    assert "Credit per write" in (d / "run" / "GPU_REPS.md").read_text()
    # the three contrasts and the receipts
    assert {"omni", "watch", "omni_vs_watch"} <= set(out["paired"]) and out["headline"]["verdict"] in (
        "SUPERIOR WITHIN GUARDRAILS", "ENERGY IMPROVEMENT WITH SERVICE TRADEOFF", "NONINFERIOR / INCONCLUSIVE", "NOT ESTABLISHED", "WORSE")
    c1 = out["checks"]["omni"]["1"]
    assert c1["actuator"]["writes_ok"] > 0 and c1["actuator"]["restored_ok"] and c1["governor"]["decisions"] and c1["representation"]["pairs"]
    assert "enforced.power.limit" in (d / "run" / "rep-1" / "native" / "smi_fields.txt").read_text()
    md = (d / "run" / "GPU_REPS.md").read_text()
    assert "Authority: Omni governs against Omni watching" in md and "Actuator fidelity" in md and "Representation fidelity" in md
    # a native arm whose enforced limit moved away from the snapshot makes the run invalid
    f = d / "run" / "rep-1" / "native" / "smi.csv"; keep = f.read_text()
    f.write_text("\n".join(",".join(r.split(",")[:7] + [" 150.00"] + r.split(",")[8:]) for r in keep.splitlines()) + "\n")
    from tools.gpu_reps import main as reps1
    assert reps1(str(d / "run")) == 2 and any("enforced" in x for x in json.loads((d / "run" / "GPU_REPS.json").read_text())["problems"])
    f.write_text(keep)
    # a watch arm that wrote makes the run invalid
    with open(d / "run" / "rep-1" / "watch" / "audit.jsonl", "a") as f:
        f.write(json.dumps({"write": ["nvidia-smi", "-i", "0", "-pl", "250"]}) + "\n")
    from tools.gpu_reps import main as reps
    assert reps(str(d / "run")) == 2


def bench_bowl():
    """The paired run with the two-wire engine (the default Omni arm): valid, watch writes nothing, Omni moves both wires,
    and the card's clock range and power limit are back at the start after every arm."""
    d = Path(tempfile.mkdtemp())
    state(d)
    env = dict(os.environ, NVIDIA_SMI=SMI, SIM="1", REPS="2", DURATION="20", DRAIN="1", COOLDOWN="0", INTERVAL="1",
               SAMPLE_MS="200", OUT=str(d / "run"), WORKLOAD_ARGS="--calib 5 --target-ms 20")
    r = subprocess.run(["bash", str(ROOT / "scripts" / "gpu_paired.sh")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    out = json.loads((d / "run" / "GPU_REPS.json").read_text())
    assert not out["problems"], out["problems"]
    assert {c["writes"] for c in out["checks"]["watch"].values()} == {0}
    recs = [json.loads(x) for x in open(d / "run" / "rep-1" / "omni" / "audit.jsonl") if x.strip()]
    assert any("clock_write" in x and "-lgc" in x["clock_write"] for x in recs), "the up wire never moved"
    assert any("would_clock_write" in json.loads(x) or "decision" in json.loads(x)
               for x in open(d / "run" / "rep-1" / "watch" / "audit.jsonl") if x.strip())
    rest = [x for x in recs if "restored" in x][-1]
    assert rest["ok"] and any(x.get("clock_write") == ["-i", "0", "-rgc"] and x.get("why") == "restore" for x in recs)
    st = json.loads(Path(os.environ["FAKE_SMI_STATE"]).read_text())
    assert not st.get("clock_lock", {}).get("0"), "clocks left locked after the run"
    assert out["headline"]["valid"]


def wire_check():
    """The wire check passes on a card wired right and stops, naming the step, on a dead or refused clock wire."""
    for extra, want, step in (({}, 0, "WIRED RIGHT"), ({"ignore_lgc": True}, 1, "3 up wire (follows down)"),
                              ({"refuse_lgc": True}, 1, "3 up wire (lock)")):
        d = Path(tempfile.mkdtemp()); p = state(d, limit={"0": 150.0}, default=150, max=150, draw_w=140.0, **extra)
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "gpu_wire_check.py"), "--smi", SMI], cwd=ROOT,
                           env=dict(os.environ, SIM="1", WIRE_SETTLE="0.2"), capture_output=True, text=True, timeout=120)
        assert r.returncode == want and step in r.stdout, r.stdout[-1500:] + r.stderr[-800:]
        st = json.loads(p.read_text())
        assert st["limit"]["0"] == 150.0 and not st.get("clock_lock", {}).get("0"), "the check left the card off its start"


def pooled():
    """Repetitions spread over machines (REP_ONLY): each machine's run carries its own records; pooled, they make one
    valid table."""
    import shutil
    d = Path(tempfile.mkdtemp()); state(d)
    for k in (1, 2):
        env = dict(os.environ, NVIDIA_SMI=SMI, SIM="1", REP_ONLY=str(k), DURATION="4", DRAIN="1", COOLDOWN="0", INTERVAL="1",
                   SAMPLE_MS="200", OUT=str(d / f"m{k}"), WORKLOAD_ARGS="--calib 5 --target-ms 20", OMNI_ENGINE="one_wire")
        if k == 2:   # the second machine serves an outside workload through the plug (here the pinned one, invoked as a command)
            env.update(SLO_MS="200", WORKLOAD_CMD="python3 tools/gpu_workload.py calibrate --out \"$OUT_DIR\" --sim --calib 5 --target-ms 20 "
                       "&& python3 tools/gpu_workload.py run --calib-file \"$OUT_DIR/calib.json\" --out \"$OUT_DIR\" --duration \"$DURATION\" --drain \"$DRAIN\"")
        r = subprocess.run(["bash", str(ROOT / "scripts" / "gpu_paired.sh")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
        shutil.copytree(d / f"m{k}" / f"rep-{k}", d / "pool" / f"rep-{k}")
    from tools.gpu_reps import main as reps
    assert reps(str(d / "pool")) == 0
    out = json.loads((d / "pool" / "GPU_REPS.json").read_text())
    assert sorted(out["checks"]["omni"]) == ["1", "2"] and not out["problems"]
    assert (d / "pool" / "rep-2" / "workload_cmd.txt").exists() and json.loads((d / "pool" / "rep-2" / "receipt.json").read_text())["workload_cmd"]


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


def lock():
    """The speed lock: response time against a run without Omni at the same arrival rate. Over the line (0.99): the
    start limit at once; under the line less the margin: a step down, sized by the slack, at most once per hold;
    in between: held. Off unless a baseline file is given."""
    from omni_controller.gpu_governor import GpuGovernor, window_stats, baseline_at
    d = Path(tempfile.mkdtemp()); p = state(d, draw_w=150.0, util=40)
    base = {"bins": [{"rate": 5.0, "mean": 100.0, "p95": 200.0, "p99": 300.0}, {"rate": 15.0, "mean": 200.0, "p95": 400.0, "p99": 600.0}]}
    assert baseline_at(base, 10.0) == {"mean": 150.0, "p95": 300.0, "p99": 450.0} and baseline_at(base, 1.0)["mean"] == 100.0
    (d / "base.json").write_text(json.dumps(base)); lat = d / "lat.csv"
    def probe(scale):                       # 600 requests over 60 s (10 per second), latencies scale x the baseline
        rows = [(i / 10.0, 150.0 * scale * (0.5 + (i % 100) / 99.0)) for i in range(600)]
        lat.write_text("elapsed_seconds,latency_ms,ok\n" + "".join(f"{t:.1f},{m:.2f},1\n" for t, m in rows))
    probe(0.5); st = window_stats(str(lat), 60.0)
    assert abs(st["rate"] - 10.0) < 0.2 and st["n"] == 600, st
    g = GpuGovernor(args(d, "cap", baseline_file=str(d / "base.json"), speed_gain=0.01, lock_margin=0.08, lock_step=0.02,
                         lock_boost=5.0, lock_window_s=60.0, lock_floor=0.5, lock_hold_s=10.0, latency_file=str(lat), slo_ms=0.0))
    t = [0.0]; g.clock = lambda: t[0]
    lim = lambda: json.load(open(p))["limit"]["0"]
    probe(0.5); g.step()
    assert lim() == 270.0, "half the baseline's response time: a boosted step down, 5 x 2% of 300 W"
    probe(0.5); g.step()
    assert lim() == 270.0, "inside the hold: no second step"
    t[0] = 11.0; probe(0.5); g.step()
    assert lim() == 240.0, "after the hold: the next step"
    t[0] = 22.0; probe(0.95); g.step()
    assert lim() == 240.0, "between the line and the margin: held"
    t[0] = 33.0; probe(1.05); g.step()
    assert lim() == 300.0, "slower than the line: the start limit at once"
    last = [x for x in recs(d / "audit-cap.jsonl") if "decision" in x][-1]["decision"]["0"]
    assert last["shield_bound"] == "speed_lock_release" and last["speed_lock"]["line"] == 0.99, last
    lat.unlink(); t[0] = 44.0; g.step()
    assert lim() == 300.0, "blind: the start limit"


def enforced():
    """The card obeys enforced.power.limit: snapshot of every limit, the engine senses the enforced one, each write read
    back at once with an override recorded; cap mode refused without power management; a refused write ends the arm
    (exit 4, start limit restored); a driver without the field falls back to power.limit and says so; result labels by rule."""
    from omni_controller.gpu_governor import GpuGovernor, main as gmain
    from tools.gpu_reps import label
    d = Path(tempfile.mkdtemp())
    p = state(d, enforced_cap=250.0)
    g = GpuGovernor(args(d, "cap", audit=str(d / "a1.jsonl")))
    snap = recs(d / "a1.jsonl")[0]
    s0 = snap["snapshot"]["0"]
    assert s0["enforced_w"] == 250.0 and s0["power.management"] == "Enabled" and s0["power.max_limit"] == "350", s0
    assert snap["senses"] == "enforced.power.limit"
    for _ in range(3):
        g.step()
    dec = [x for x in recs(d / "a1.jsonl") if "decision" in x][0]["decision"]["0"]
    assert dec["telemetry"]["enforced_w"] == 250.0 and dec["telemetry"]["limit_w"] == 300.0 and "u_push" in dec and "state_measured" in dec
    act = [x["actuator"] for x in recs(d / "a1.jsonl") if "actuator" in x]
    assert act and act[0]["rc"] == 0 and act[0]["realized"] and act[0]["readback_w"] == act[0]["requested_w"] and "delay_s" in act[0], act
    assert g.restore()
    # the card's own controller already holds it at 200 W: a write of 234 W (above 200) would change nothing; not written
    p = state(d, enforced_cap=200.0)
    g = GpuGovernor(args(d, "cap", audit=str(d / "a2.jsonl"))); g.step()
    a2 = recs(d / "a2.jsonl")
    assert not any("write" in x for x in a2) and json.load(open(p))["limit"]["0"] == 300.0, a2[-1]
    assert [x for x in a2 if "decision" in x][0]["decision"]["0"]["outer_controller_holds"] is True
    g.restore()
    # a write that does bind under an outer hold (enforced 260, want 234) goes out, and the override is recorded
    p = state(d, enforced_cap=260.0)
    g = GpuGovernor(args(d, "cap", audit=str(d / "a2b.jsonl"))); g.step()
    assert json.load(open(p))["limit"]["0"] == 234.0
    g.restore()
    # the declared envelope floor: never under it (draw would allow 234 W; the floor is 270 W)
    p = state(d)
    g = GpuGovernor(args(d, "cap", audit=str(d / "a2c.jsonl"), floor_w=270.0)); g.step()
    assert json.load(open(p))["limit"]["0"] == 270.0
    dc = [x for x in recs(d / "a2c.jsonl") if "decision" in x][0]["decision"]["0"]
    assert dc["decided_by"] == "envelope_floor" and "envelope_floor" in dc["blocked_by"], dc
    g.restore()
    # power management off: cap refused before any write; watch still allowed
    state(d, management="Disabled")
    try:
        GpuGovernor(args(d, "cap", audit=str(d / "a3.jsonl"))); raise AssertionError("cap mode ran without power management")
    except SystemExit as e:
        assert "power management" in str(e)
    assert "refused" in recs(d / "a3.jsonl")[-1] and not Path(os.environ["FAKE_SMI_STATE"] + ".writes").exists()
    GpuGovernor(args(d, "watch", audit=str(d / "a3w.jsonl")))
    # a refused write ends the arm: recorded, restored, exit 4
    p = state(d, refuse_pl=True)
    rc = gmain(["--mode", "cap", "--smi", SMI, "--audit", str(d / "a4.jsonl"), "--kill-file", str(d / "nokill"),
                "--interval", "0.2", "--duration", "5", "--min-share", "0", "--util-gate", "0"])
    r4 = recs(d / "a4.jsonl")
    assert rc == 4 and any("write_failed" in x for x in r4) and any("fatal" in x for x in r4), (rc, r4[-3:])
    assert r4[-1]["restored"]["0"] == 300.0 and r4[-1]["ok"] is True
    # a driver without enforced.power.limit: power.limit, and the snapshot says so
    state(d, no_enforced=True)
    g = GpuGovernor(args(d, "watch", audit=str(d / "a5.jsonl")))
    a5 = recs(d / "a5.jsonl")[0]
    assert not g.enforced_ok and a5["senses"].startswith("power.limit") and a5["snapshot"]["0"]["enforced.power.limit"] == "unsupported"
    g.step()
    assert [x for x in recs(d / "a5.jsonl") if "decision" in x][0]["decision"]["0"]["telemetry"]["enforced_w"] == 300.0
    # result labels, by rule
    assert label("better, proven", True, True, True, True) == "SUPERIOR WITHIN GUARDRAILS"
    assert label("better, proven", True, False, True, True) == "ENERGY IMPROVEMENT WITH SERVICE TRADEOFF"
    assert label("better, not proven", True, True, True, True) == "NONINFERIOR / INCONCLUSIVE"
    assert label("worse, not proven", False, True, True, True) == "NOT ESTABLISHED"
    assert label("worse, proven", True, True, True, True) == "WORSE"
    assert label("better, proven", True, True, True, False) == "INVALID"


def one_writer():
    """One writer: a limit changed by anyone else stops Omni writing (observe only), leaves the other writer's limit
    alone on kill, and exits 5. Heat: a reported thermal or hardware slowdown never gets a tighter limit. Every decision
    names what blocked the engine and what decided. RAPL: package and DRAM summed apart, psys kept out, wrap handled,
    missing counters UNAVAILABLE; the governor never reads the energy counters."""
    from omni_controller.gpu_governor import GpuGovernor, main as gmain, slowed, blocked_by
    from tools.gpu_reps import rapl_energy, rapl_delta
    d = Path(tempfile.mkdtemp())
    p = state(d)
    g = GpuGovernor(args(d, "cap", audit=str(d / "b1.jsonl"))); g.step()
    assert json.load(open(p))["limit"]["0"] == 234.0
    S = json.load(open(p)); S["limit"]["0"] = 280.0; json.dump(S, open(p, "w"))       # someone else writes -pl
    g.step(); g.step()
    r = recs(d / "b1.jsonl")
    assert any("foreign_writer" in x for x in r) and g.foreign, r[-2:]
    assert json.load(open(p))["limit"]["0"] == 280.0, "Omni must not fight the other writer"
    assert any(x.get("withheld") for x in r) or not any("write" in x for x in r[-3:])
    g.restore(); assert json.load(open(p))["limit"]["0"] == 280.0 and recs(d / "b1.jsonl")[-1]["foreign_writer"] is True
    # decisions name the blocker and the decider
    dec = [x for x in r if "decision" in x and "blocked_by" in x["decision"].get("0", {})][0]["decision"]["0"]
    assert "draw_headroom_floor" in dec["blocked_by"] and dec["decided_by"] in ("draw_headroom_floor", "share_floor"), dec
    assert blocked_by(0.5, 100, 300, 100, 0.3, 0.7, True, False, True, False) == ["share_floor", "thermal_hold"]
    # heat: 0x40 (HW thermal slowdown) set, the limit is not lowered
    assert slowed("0x0000000000000040") and not slowed("0x0000000000000004") and not slowed(None)
    p = state(d, draw_w=100.0, util=10)
    import omni_controller.gpu_governor as GG
    real = GG.throttle; GG.throttle = lambda smi, gpus: {0: "0x0000000000000040"}
    try:
        g = GpuGovernor(args(d, "cap", audit=str(d / "b2.jsonl"), min_share=0.0, util_gate=0.0)); g.step()
    finally:
        GG.throttle = real
    assert json.load(open(p))["limit"]["0"] == 300.0
    assert [x for x in recs(d / "b2.jsonl") if "decision" in x][0]["decision"]["0"]["decided_by"] == "thermal_hold"
    # RAPL: two packages, a DRAM child, psys; package 1 wrapped
    a = d / "arm"; a.mkdir()
    (a / "rapl_start.tsv").write_text("intel-rapl:0 package-0 1000000 262143328850\nintel-rapl:1 package-1 262143000000 262143328850\n"
                                      "intel-rapl:0:2 dram 500000 65532610987\nintel-rapl:2 psys 7000000 262143328850\n")
    (a / "rapl_end.tsv").write_text("intel-rapl:0 package-0 3000000 262143328850\nintel-rapl:1 package-1 671150 262143328850\n"
                                    "intel-rapl:0:2 dram 1500000 65532610987\nintel-rapl:2 psys 17000000 262143328850\n")
    e = rapl_energy(a)
    assert abs(e["energy, CPU package (J)"] - 3.0) < 1e-6 and abs(e["energy, DRAM (J)"] - 1.0) < 1e-9 and abs(e["energy, platform psys (J)"] - 10.0) < 1e-9, e
    assert rapl_delta(10, 5, 0) is None
    assert all(v != v for v in rapl_energy(d / "nowhere").values()), "missing counters: UNAVAILABLE, never zero"
    assert "powercap" not in (ROOT / "omni_controller" / "gpu_governor.py").read_text() and "energy_uj" not in (ROOT / "omni_controller" / "gpu_governor.py").read_text()


def main():
    plugs(); governor(); guards(); lock(); enforced(); one_writer(); bench(); bench_bowl(); wire_check(); pooled()
    print("PASS  GPU bench: governor contract (watch writes nothing, shield floor, share floor, busy gate, read-back, blind, SLO reflex, kill), "
          "enforced limit (snapshot, override, power management, refused write ends the arm, fallback), one writer, heat fails up, blocked_by and decided_by, RAPL by domain, credit per write, workload plug, result labels, "
          "and the one-command paired run with its validity checks")


if __name__ == "__main__":
    main()
