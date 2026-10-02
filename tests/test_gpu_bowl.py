# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The two-wire GPU governor (omni_controller/gpu_bowl.py) against the stand-in nvidia-smi (tests/fake_gpu/nvidia-smi),
on a card its own power limit holds at 900 MHz while busy (top clock 1695 MHz), with calm response times:

  learn     until the card's own busy clock and draw are learned, neither wire moves below where the card is
  floor     after that, the clock ceiling never goes under the card's own busy clock, so waiting work is never served
            slower than native; the lid never goes under the card's own busy draw plus headroom
  race      a saturated card (work waiting) runs at full speed, ceiling at the top and the lid at the start; it is not a
            fail-up, and it is where the card's own level is learned
  pace      at partial load with calm response times the bowl lowers the ceiling, never under the learned busy clock
  hot       response times past the line: fail up, ceiling to the top and the lid to the start limit
  restore   clocks reset and the start limit back at the end
"""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omni_controller.gpu_bowl import GpuBowl, parser
SMI = str(ROOT / "tests" / "fake_gpu" / "nvidia-smi")


def setup(tmp, util=100):
    st = {"limit": {"0": 150.0}, "default": 150.0, "min": 100.0, "max": 150.0, "draw_w": 220.0, "util": util, "temp": 60,
          "clock_top": 1695.0, "busy_clock": 900.0}
    p = Path(tmp) / "smi.json"; p.write_text(json.dumps(st)); os.environ["FAKE_SMI_STATE"] = str(p)
    return p


def latency(tmp, ms):
    f = Path(tmp) / "latency.csv"
    f.write_text("elapsed_seconds,latency_ms,ok\n" + "".join(f"{i * 0.2},{ms},1\n" for i in range(60))); os.utime(f, None)
    return f


def gov(tmp, lat):
    a = parser().parse_args(["--mode", "cap", "--gpus", "0", "--smi", SMI, "--interval", "1", "--audit", str(Path(tmp) / "a.jsonl"),
                             "--kill-file", str(Path(tmp) / "kill"), "--latency-file", str(lat), "--slo-ms", "800",
                             "--floor-w", "105", "--learn-samples", "5"])
    return GpuBowl(a)


def decisions(tmp):
    return [json.loads(l)["decision"]["0"] for l in (Path(tmp) / "a.jsonl").read_text().splitlines() if '"decision"' in l]


def main():
    t = tempfile.mkdtemp(); st = setup(t, util=100); lat = latency(t, 100.0)
    g = gov(t, lat)
    for _ in range(10):
        latency(t, 100.0); g.step()
    d = decisions(t)
    assert all(x["decided_by"] == "race" and x["ceiling_mhz"] >= 1695 and x["want_w"] >= 150 for x in d), "saturated but not racing"
    print("saturated: race at full speed (ceiling at the top, lid at the start) while the card's own level is learned")
    s = json.loads(st.read_text()); s["util"] = 70; st.write_text(json.dumps(s))
    for _ in range(40):
        latency(t, 100.0); g.step()
    d = decisions(t)
    assert all(x["decided_by"] not in ("fail_up",) for x in d), "calm response times read as past the wall"
    n_clk = d[-1]["native_busy_clock_mhz"]; n_draw = d[-1]["native_busy_draw_w"]
    assert n_clk == 900.0, n_clk
    assert min(x["ceiling_mhz"] for x in d) >= 900, "the ceiling went under the card's own busy clock"
    assert min(x["want_w"] for x in d) >= min(150, int(n_draw * 1.10)), "the lid went under the card's own busy draw"
    s = json.loads(st.read_text())
    print(f"calm and busy: no fail-up; learned busy clock {n_clk:.0f} MHz, busy draw {n_draw:.1f} W; ceiling low "
          f"{min(x['ceiling_mhz'] for x in d)} MHz (never under 900), lid low {min(x['want_w'] for x in d)} W; limit now {s['limit']['0']} W")
    for _ in range(3):
        latency(t, 900.0); g.step()
    d = decisions(t)
    assert d[-1]["decided_by"] == "fail_up" and d[-1]["ceiling_mhz"] >= 1695 and d[-1]["want_w"] >= 150
    print("hot (p95 past the line): fail up, ceiling to the top, lid to the start limit")
    assert g.restore()
    s = json.loads(st.read_text())
    assert s["limit"]["0"] == 150.0 and "0" not in s.get("clock_lock", {})
    print("restore: clocks reset, limit back to 150 W")
    print("PASS two-wire GPU governor: never slower than the card on its own while it works")


if __name__ == "__main__":
    main()
