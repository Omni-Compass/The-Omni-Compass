#!/usr/bin/env python3
"""Read-only CPUFreq receipt for a prospective Omni hardware run."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hardware.cpufreq import CpuFreqPolicies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/sys/devices/system/cpu/cpufreq")
    ap.add_argument("--out", default="results/hardware/CPUFREQ_RECEIPT.json")
    a = ap.parse_args()
    c = CpuFreqPolicies(a.root)
    rows = c.snapshot()
    obj = {
        "evidence_type": "read_only_cpufreq_sysfs_receipt",
        "root": str(a.root),
        "policies": [r.as_dict() for r in rows],
        "schedutil_all": bool(rows) and all(r.scaling_governor == "schedutil" for r in rows),
        "note": "A ceiling write is not an observation of delivered silicon frequency. Active intel_pstate/HWP is a separate driver lane.",
    }
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(obj, indent=2) + "\n")
    print(json.dumps(obj, indent=2))
    if not rows:
        raise SystemExit("no CPUFreq policies found")


if __name__ == "__main__": main()
