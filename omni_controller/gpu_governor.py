"""Omni-Compass on one GPU box, no Kubernetes: the engine reads each GPU's own meter and may lower its power limit.

Every decision (--interval seconds), for each GPU in --gpus:
  sense     nvidia-smi: power.draw, temperature.gpu, utilization.gpu, power.limit (the device's own readings)
            the workload's response-time file (--latency-file, elapsed_seconds,latency_ms,ok) if given
  engine    the Omni-Compass governor, throughput law (omnicompass/adapter.py): load = utilization, power stress =
            draw / the limit found at start, heat = temperature / --temp-limit, queue = response-time pressure.
            Its directive power_cap is the share of the start limit the GPU may draw.
  shield    limit = max(cap x start limit, draw x (1 + --headroom), --min-share x start limit, the device's minimum
            limit), never above the start limit; whole watts; a change under --min-change-w is not written.
            --min-share bounds the slowdown: a card held at that share of its limit runs a burst only a little slower.
  busy gate utilization (smoothed over decisions) at or above --util-gate: the start limit. A busy card is the
            bottleneck; slowing it grows the queue faster than it saves energy. The cap returns once utilization is
            back under the gate less --util-band.
  reflexes  a blind sense (nvidia-smi unreadable, or the response-time file stale or empty): the start limit, at once
            a response-time breach (p95 > --slo-ms), and for --slo-clear decisions after it: the start limit, at once
  read-back no new write until the last one is read back from the device (power.limit within 1 W of what I wrote)
  speed lock (--baseline-file, from tools/gpu_baseline.py on a run without Omni): the limit is set by response time
            alone. Over the last --lock-window-s of the response-time file, the mean, 95th and 99th percentile are each
            divided by the baseline's at the same arrival rate; the worst of the three is the speed ratio. The line is
            1 - --speed-gain (0.99: at least 1% faster than without Omni). Above the line: the start limit, at once.
            Under the line less --lock-margin: lower by --lock-step x start, times the slack in margins (up to
            --lock-boost), at most once per --lock-hold-s (the window must see the step before the next). Between: held. Never under --lock-floor x start.
            Speed won elsewhere (CPU conveyed to the serving pods, shorter queues) shows as a ratio under the line,
            and the lock spends it on watts; with nothing won elsewhere it holds the start limit.
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


def window_stats(path, window_s, now=None):
    """Mean, 95th and 99th percentile (ms) and arrival rate (served per second) of the successful requests in the last
    window_s of the response-time file; None when blind (stale beyond two windows, or under 20 requests)."""
    try:
        age = (now if now is not None else time.time()) - os.path.getmtime(path)
        rows = [l.split(",") for l in Path(path).read_text().splitlines()[1:] if l.strip()]
    except OSError:
        return None
    if not rows or age > 2.0 * window_s:
        return None
    t_end = float(rows[-1][0])
    ms = sorted(float(r[1]) for r in rows if float(r[0]) >= t_end - window_s and r[2].strip() == "1")
    if len(ms) < 20:
        return None
    span = min(window_s, max(1.0, t_end - float(rows[0][0])))
    return {"mean": sum(ms) / len(ms), "p95": ms[min(len(ms) - 1, int(0.95 * len(ms)))],
            "p99": ms[min(len(ms) - 1, int(0.99 * len(ms)))], "rate": len(ms) / span, "n": len(ms)}


def baseline_at(base, rate):
    """The baseline's mean, p95 and p99 at an arrival rate, linear between its rate bins, flat beyond the ends."""
    bins = base["bins"]
    if rate <= bins[0]["rate"]:
        return bins[0]
    if rate >= bins[-1]["rate"]:
        return bins[-1]
    for lo, hi in zip(bins, bins[1:]):
        if lo["rate"] <= rate <= hi["rate"]:
            f = (rate - lo["rate"]) / (hi["rate"] - lo["rate"])
            return {k: lo[k] + f * (hi[k] - lo[k]) for k in ("mean", "p95", "p99")}


def shield_limit(cap, draw, start, min_w, headroom, min_share, slo_clean):
    """The shield: limit = max(cap x start, draw x (1 + headroom), min_share x start, device minimum), never above start,
    whole watts. Returns (want_w, the bound that decided it). Twinned in C++ (cpp/src/gpu_rules.cpp)."""
    share_floor = min_share * start
    floor = max(draw * (1.0 + headroom), min_w, share_floor)
    engine_w = math.floor(cap * start)
    want = int(min(start, max(engine_w, math.ceil(floor))))
    bound = ("slo_or_blind_reflex" if not slo_clean else "start_ceiling" if want >= start and engine_w >= start
             else "share_floor" if math.ceil(floor) > engine_w and floor == share_floor
             else "draw_headroom_floor" if math.ceil(floor) > engine_w and floor > min_w
             else "device_minimum" if math.ceil(floor) > engine_w else "engine")
    return want, bound


def busy_gate(u_prev, util, gated_prev, gate, band):
    """Utilization smoothed over decisions (u_prev None: the first reading) and the gate with its band. Returns
    (u, gated). Twinned in C++."""
    u = 0.5 * (util if u_prev is None else u_prev) + 0.5 * util
    return u, (u >= gate or (gated_prev and u >= gate - band))


def lock_decide(ratio, cur, start, min_w, since_last, speed_gain, lock_margin, lock_step, lock_boost, lock_floor, lock_hold_s):
    """The speed lock's step from the worst response-time ratio against the baseline. Returns (want_w, bound, line,
    aim). Twinned in C++."""
    line = 1.0 - speed_gain
    aim = line * (1.0 - lock_margin)
    floor = max(min_w, lock_floor * start)
    if ratio > line:
        want, bound = start, "speed_lock_release"
    elif ratio < aim and since_last >= lock_hold_s:
        mult = min(lock_boost, max(1.0, (aim - ratio) / max(1e-6, line * lock_margin)))
        want, bound = max(floor, cur - mult * lock_step * start), "speed_lock_spend"
    else:
        want, bound = cur, "speed_lock_hold"
    return int(min(start, max(floor, want))), bound, line, aim


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
        self.reasons_ok = True     # False once the driver shows it does not report clock-limit reasons
        self.util_avg = {}         # gpu -> utilization smoothed over decisions (busy gate)
        self.gated = {}            # gpu -> True while the busy gate holds the start limit
        bf = getattr(a, "baseline_file", "")
        self.baseline = json.loads(Path(bf).read_text()) if bf else None   # speed lock: the run without Omni
        self.lock_at = {}          # gpu -> time of the lock's last change
        self.clock = time.time     # replaceable, so a simulation in virtual time can drive the lock's hold
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

    def speed_lock(self, g, cur, slo_clean):
        """The limit from response time against the run without Omni (see the module docstring). Returns
        (want_w, bound, why, record)."""
        a, start = self.a, self.start[g]
        st = window_stats(a.latency_file, a.lock_window_s) if a.latency_file else None
        if st is None or not slo_clean:
            return int(start), "speed_lock_blind", "speed lock: no response-time window (or SLO reflex), the start limit", None
        b = baseline_at(self.baseline, st["rate"])
        ratios = {k: st[k] / b[k] for k in ("mean", "p95", "p99")}
        ratio = max(ratios.values())
        want, bound, line, aim = lock_decide(ratio, cur, start, self.min[g], self.clock() - self.lock_at.get(g, -1e18),
                                             a.speed_gain, a.lock_margin, a.lock_step, a.lock_boost, a.lock_floor, a.lock_hold_s)
        if want != int(cur):
            self.lock_at[g] = self.clock()
        rec = {"rate": round(st["rate"], 2), "ratios": {k: round(v, 4) for k, v in ratios.items()},
               "line": line, "aim": round(aim, 4), "n": st["n"]}
        why = f"speed lock: worst ratio {ratio:.3f} vs line {line:.3f} ({bound.split('_')[-1]}), limit {want} W"
        return want, bound, why, rec

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
                want, bound = shield_limit(cap, r["draw"], self.start[g], self.min[g], a.headroom, getattr(a, "min_share", 0.0), slo_clean)
                gate = getattr(a, "util_gate", 0.0)
                if gate:
                    self.util_avg[g], self.gated[g] = busy_gate(self.util_avg.get(g), r["util"], self.gated.get(g, False),
                                                                gate, getattr(a, "util_band", 0.1))
                    if self.gated[g]:
                        want, bound = int(self.start[g]), "busy_gate"
                        cap = 1.0
                why = ("response-time reflex: the limit read at start" if not slo_clean
                       else f"busy gate: utilization {self.util_avg[g]:.2f}, the limit read at start" if bound == "busy_gate"
                       else f"engine cap {cap:.3f} of {self.start[g]:.0f} W; floor draw {r['draw']:.0f} W x {1 + a.headroom:.2f}, "
                            f"share floor {getattr(a, 'min_share', 0.0):.2f}")
                lock = None
                if self.baseline is not None:
                    want, bound, why, lock = self.speed_lock(g, cur, slo_clean)
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
                    "engine_cap": round(requested, 3), "E": round(d["state"]["E"], 3), "U": round(d["state"]["U"], 3),
                    "speed_lock": lock}
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
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--duration", type=float, default=0.0, help="seconds to run (0: until killed)")
    ap.add_argument("--audit", default="gpu_audit.jsonl")
    ap.add_argument("--kill-file", default="/tmp/omni-gpu-kill")
    ap.add_argument("--headroom", type=float, default=0.3, help="limit never below draw x (1 + headroom)")
    ap.add_argument("--min-share", type=float, default=0.70, help="limit never below this share of the start limit (0: off)")
    ap.add_argument("--util-gate", type=float, default=0.5, help="smoothed utilization at which the start limit returns (0: off)")
    ap.add_argument("--util-band", type=float, default=0.1, help="the cap resumes below --util-gate less this band")
    ap.add_argument("--baseline-file", default="", help="speed lock: baseline from tools/gpu_baseline.py (off when empty)")
    ap.add_argument("--speed-gain", type=float, default=0.01, help="speed lock line: at least this much faster than baseline")
    ap.add_argument("--lock-boost", type=float, default=5.0, help="largest multiple of --lock-step in one step down")
    ap.add_argument("--lock-margin", type=float, default=0.08, help="spend watts only while this far under the line")
    ap.add_argument("--lock-step", type=float, default=0.02, help="share of the start limit given up per decision")
    ap.add_argument("--lock-hold-s", type=float, default=10.0, help="seconds between two steps down")
    ap.add_argument("--lock-window-s", type=float, default=60.0, help="response-time window the lock reads")
    ap.add_argument("--lock-floor", type=float, default=0.5, help="the lock never holds the limit under this share of start")
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
