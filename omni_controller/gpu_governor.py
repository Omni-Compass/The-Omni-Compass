"""Omni-Compass on one GPU box, no Kubernetes: the engine reads each GPU's own meter and may lower its power limit.

Every decision (--interval seconds), for each GPU in --gpus:
  sense     nvidia-smi: power.draw, temperature.gpu, utilization.gpu, power.limit (the device's own readings)
            the workload's response-time file (--latency-file, elapsed_seconds,latency_ms,ok) if given
  engine    the Omni-Compass governor, throughput law (omnicompass/adapter.py): load = utilization, power stress =
            draw / the limit found at start, heat = temperature / --temp-limit, queue = response-time pressure.
            Its directive power_cap is the share of the start limit the GPU may draw.
  shield    limit = max(cap x start limit, draw x (1 + --headroom), the device's minimum limit), never above the start
            limit; whole watts; a change under --min-change-w is not written
  reflexes  a blind sense (nvidia-smi unreadable, or the response-time file stale or empty): the start limit, at once
            a response-time breach (p95 > --slo-ms), and for --slo-clear decisions after it: the start limit, at once
  read-back no new write until the last one is read back from the device (power.limit within 1 W of what I wrote)
Modes
  watch     everything above is computed and audited; nothing is written (the control arm)
  cap       the limit is written with nvidia-smi -i <gpu> -pl <W>
Kill switch
  the kill file (or SIGTERM) restores every GPU to the limit read at start, reads it back, and exits.
  The start limits are recorded first in the audit ("snapshot").
"""
from __future__ import annotations

import argparse, copy, json, math, os, shlex, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnicompass.adapter import Governor, mode_law, AUTOPILOT, OBSERVE, observe_vector, assimilate
from omni_controller.muscles import latency_sense

FIELDS = "index,power.draw,temperature.gpu,utilization.gpu,power.limit,power.min_limit,clocks.sm"
REASONS = ("clocks_event_reasons.active", "clocks_throttle_reasons.active")   # newer, older drivers
STATE = ("E", "U", "I_U", "S", "B", "B_dot")


def throttle(smi, gpus):
    """The device's own record of why its clock is held down (power cap, thermal, ...), as a bit mask; None if the
    driver does not report it."""
    for f in REASONS:
        try:
            out = subprocess.run(shlex.split(smi) + [f"--query-gpu=index,{f}", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=10, check=True).stdout
            return {int(x.split(",")[0]): x.split(",")[1].strip() for x in out.strip().splitlines()}
        except (subprocess.SubprocessError, OSError, ValueError, IndexError):
            continue
    return None


def query(smi, gpus):
    """{gpu: {"draw", "temp", "util", "limit", "min"}} from the device, or None if nvidia-smi cannot be read."""
    try:
        out = subprocess.run(shlex.split(smi) + [f"--query-gpu={FIELDS}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, check=True).stdout
        rows = {}
        for line in out.strip().splitlines():
            v = [x.strip() for x in line.split(",")]
            rows[int(v[0])] = {"draw": float(v[1]), "temp": float(v[2]), "util": float(v[3]) / 100.0,
                               "limit": float(v[4]), "min": float(v[5]), "clock_mhz": float(v[6])}
        return {g: rows[g] for g in gpus} if all(g in rows for g in gpus) else None
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        return None


class GpuGovernor:
    def __init__(self, a):
        self.a = a
        self.gpus = [int(g) for g in str(a.gpus).split(",") if g.strip() != ""]
        self.log = open(a.audit, "a")
        self.eng = {g: Governor(law=mode_law("throughput")) for g in self.gpus}
        for e in self.eng.values():
            e.set_mode(AUTOPILOT if a.mode == "cap" else OBSERVE)
            e.nodes = 1
        self.cap = {g: 1.0 for g in self.gpus}
        self.written = {}          # gpu -> last limit written (W), until read back
        self.lp_hist = []
        self.writes = 0
        self.projected = {}
        self.reasons_ok = True     # False once the driver shows it does not report clock-limit reasons        # gpu -> the engine state I projected for the next decision
        s = query(a.smi, self.gpus)
        if s is None:
            raise SystemExit("nvidia-smi unreadable at start: no snapshot, so I take no authority")
        self.start = {g: s[g]["limit"] for g in self.gpus}
        self.min = {g: s[g]["min"] for g in self.gpus}
        self.audit({"snapshot": {str(g): {"limit_w": self.start[g], "min_limit_w": self.min[g]} for g in self.gpus},
                    "mode": a.mode})

    def audit(self, rec):
        self.log.write(json.dumps({"time": time.time(), **rec}) + "\n"); self.log.flush()

    def set_limit(self, g, w, why):
        cmd = ["nvidia-smi", "-i", str(g), "-pl", str(int(w))]
        if self.a.mode != "cap":
            self.audit({"would_write": cmd, "why": why})     # watch: computed and recorded, never executed
            return
        self.audit({"write": cmd, "why": why})
        subprocess.run(shlex.split(self.a.smi) + ["-i", str(g), "-pl", str(int(w))], capture_output=True, text=True, check=True)
        self.writes += 1
        self.written[g] = int(w)

    def killed(self):
        return os.path.exists(self.a.kill_file)

    def restore(self):
        """Kill switch: every GPU back to the limit read at start, read back from the device."""
        s = query(self.a.smi, self.gpus) or {}
        for g in self.gpus:
            if self.a.mode == "cap" and (g not in s or abs(s[g]["limit"] - self.start[g]) >= 1.0):
                self.set_limit(g, self.start[g], "kill switch: the limit read at start")
        s = query(self.a.smi, self.gpus) or {}
        back = {str(g): (s[g]["limit"] if g in s else None) for g in self.gpus}
        ok = all(v is not None and abs(v - self.start[int(g)]) < 1.0 for g, v in back.items())
        self.audit({"restored": back, "start": {str(g): self.start[g] for g in self.gpus}, "ok": ok, "writes": self.writes})
        return ok

    def step(self):
        a = self.a
        s = query(a.smi, self.gpus)
        blind = s is None
        lp, p95, served = 0.0, None, None
        if a.latency_file and a.slo_ms:
            ls = latency_sense(a.latency_file, a.latency_window_s)
            served = ls["ok"]
            blind = blind or ls["blind"]
            if not ls["blind"]:
                p95 = ls["p95"]
                lp = max(0.0, ls["p95"] / a.slo_ms - 1.0)
                if ls["fail"]:
                    lp = max(lp, ls["fail"] / (ls["ok"] + ls["fail"]))
        self.lp_hist.append(lp)
        slo_clean = not blind and len(self.lp_hist) >= a.slo_clear and all(x == 0.0 for x in self.lp_hist[-a.slo_clear:])
        thr = throttle(a.smi, self.gpus) if s is not None and self.reasons_ok else None
        self.reasons_ok = self.reasons_ok and (s is None or thr is not None)
        rec = {"decision": {}, "blind": blind, "served_in_window": served, "latency_p95_ms": p95, "latency_pressure": round(lp, 3), "slo_clean": slo_clean}
        for g in self.gpus:
            if s is None:
                # blind: no give-back of power I cannot see; the start limit, at once
                if self.cap[g] == 1.0:
                    continue
                want, why, cur = self.start[g], "blind sense: the limit read at start", None
                self.cap[g] = 1.0
            else:
                r = s[g]; cur = r["limit"]
                if g in self.written and abs(cur - self.written[g]) >= 1.0:
                    # read-back: my last write has not landed; no new order on top of it
                    rec["decision"][str(g)] = {"hold": "last write not read back", "wrote_w": self.written[g], "reads_w": cur}
                    continue
                self.written.pop(g, None)
                e = self.eng[g]; e.current_cap = min(1.0, cur / self.start[g])   # the limit the device reports, not the one I meant
                obs = {"queue_ratio": min(2.0, lp), "load_ratio": r["util"], "power_stress": r["draw"] / self.start[g],
                       "thermal": r["temp"] / a.temp_limit, "network_stress": 0.0, "drift_ratio": 0.0,
                       "stale": 0.0, "security_block": 0.0}
                # the chain, recorded whole: what the device said, the state it puts the engine in, what I had projected
                # for this moment, the projection for the next, what the engine asked for, what the shield allowed
                seen = assimilate(e.x, observe_vector(obs, 0), copy.deepcopy(e.p))
                prev = self.projected.get(g)
                d = e.step(obs, 0)
                self.projected[g] = {k: getattr(e.x, k) for k in STATE}
                requested = float(d["power_cap"])
                cap = requested if slo_clean else 1.0
                floor = max(r["draw"] * (1.0 + a.headroom), self.min[g])
                engine_w = math.floor(cap * self.start[g])
                want = int(min(self.start[g], max(engine_w, math.ceil(floor))))
                bound = ("slo_or_blind_reflex" if not slo_clean else "start_ceiling" if want >= self.start[g] and engine_w >= self.start[g]
                         else "draw_headroom_floor" if math.ceil(floor) > engine_w and floor > self.min[g]
                         else "device_minimum" if math.ceil(floor) > engine_w else "engine")
                why = (f"engine cap {cap:.3f} of {self.start[g]:.0f} W; floor draw {r['draw']:.0f} W x {1 + a.headroom:.2f}"
                       if slo_clean else "response-time reflex: the limit read at start")
                self.cap[g] = want / self.start[g]
                rec["decision"][str(g)] = {
                    "telemetry": {"util": r["util"], "draw_w": r["draw"], "temp_c": r["temp"], "limit_w": cur,
                                  "clock_mhz": r["clock_mhz"], "throttle": (thr or {}).get(g)},
                    "state_observed": {k: round(getattr(seen, k), 4) for k in STATE},
                    "state_projected_before": None if prev is None else {k: round(v, 4) for k, v in prev.items()},
                    "prediction_error": None if prev is None else {k: round(getattr(seen, k) - prev[k], 4) for k in STATE},
                    "state_projected_next": {k: round(v, 4) for k, v in self.projected[g].items()},
                    "admissible": bool(d["change_permitted"]), "requested_cap": round(requested, 4),
                    "granted_cap": round(cap, 4), "shield_bound": bound, "want_w": want,
                    "engine_cap": round(requested, 3), "E": round(d["state"]["E"], 3), "U": round(d["state"]["U"], 3)}
            if cur is not None and abs(want - cur) < a.min_change_w and not (want == self.start[g] and cur != want):
                continue
            if cur is not None and want == int(cur):
                continue
            self.set_limit(g, want, why)
        self.audit(rec)


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["watch", "cap"], default="watch")
    ap.add_argument("--gpus", default="0", help="GPU indexes, comma separated")
    ap.add_argument("--smi", default=os.environ.get("NVIDIA_SMI", "nvidia-smi"))
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--duration", type=float, default=0.0, help="seconds to run (0: until killed)")
    ap.add_argument("--audit", default="gpu_audit.jsonl")
    ap.add_argument("--kill-file", default="/tmp/omni-gpu-kill")
    ap.add_argument("--headroom", type=float, default=0.3, help="limit never below draw x (1 + headroom)")
    ap.add_argument("--min-change-w", type=float, default=5.0)
    ap.add_argument("--temp-limit", type=float, default=83.0, help="GPU temperature read as heat 1.0")
    ap.add_argument("--latency-file", default="")
    ap.add_argument("--slo-ms", type=float, default=0.0)
    ap.add_argument("--latency-window-s", type=float, default=30.0)
    ap.add_argument("--slo-clear", type=int, default=3)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    gov = GpuGovernor(a)
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("now", True))
    t0 = time.time()
    try:
        while not stop["now"] and not gov.killed() and (a.duration <= 0 or time.time() - t0 < a.duration):
            try:
                gov.step()
            except Exception as e:  # noqa: BLE001  a failed decision is logged; the kill path still runs
                gov.audit({"error": f"{type(e).__name__}: {e}"})
            end = time.time() + a.interval
            while time.time() < end and not stop["now"] and not gov.killed():
                time.sleep(0.2)
    finally:
        ok = gov.restore()
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
