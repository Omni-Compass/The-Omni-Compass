# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Declare the GPU envelope before any trial (docs/GPU_PREREGISTRATION.md, amendment 3).

  python3 tools/declare_envelope.py OUT.json [--gpu 0] [--smi nvidia-smi]

Default rule: lowest watts = max(device minimum, 70% of the limit read now); highest watts = the limit read now; the
response-time target comes from calibration (10 bare service times). The file is written once, before the bench starts,
and recorded with the run.
"""
import argparse, json, math, os, subprocess, sys


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out"); ap.add_argument("--gpu", default="0"); ap.add_argument("--smi", default=os.environ.get("NVIDIA_SMI", "nvidia-smi"))
    a = ap.parse_args(argv)
    q = lambda f: float(subprocess.run([a.smi, "-i", a.gpu, f"--query-gpu={f}", "--format=csv,noheader,nounits"],
                                       capture_output=True, text=True, check=True).stdout.strip())
    start, dmin = q("power.limit"), q("power.min_limit")
    e = {"power_min_w": max(dmin, math.ceil(0.70 * start)), "power_max_w": start,
         "rule": "amendment 3 default: max(device minimum, 70% of the limit read at declaration); "
                 "response-time target from calibration (10 service times)"}
    with open(a.out, "w") as f:
        json.dump(e, f, indent=1)
    print("envelope declared:", json.dumps(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
