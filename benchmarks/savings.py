# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Savings projection: fractional energy reductions measured in the fleet benchmark and the recorded-trace run,
applied to declared fleet profiles. The reductions come from simulation; the profiles are declared examples. The output
is a projection of annual energy, cost and CO2 differences, not a measurement.

Reductions are taken against HPA 0.7 + Karpenter-lite (the stronger baseline) for the energy-first setting, with low /
high bounds from the paired 95% interval of the energy difference.
"""
import csv, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    # name, nodes, average kW per node at the wall before PUE, PUE, USD per kWh, kg CO2 per kWh
    ("cluster_1k_nodes", 1000, 0.40, 1.40, 0.12, 0.40),
    ("fleet_100k_nodes", 100000, 0.40, 1.30, 0.08, 0.40),
]


GPU_NODE_KW = 6.0  # declared average draw of an 8-GPU node before PUE, applied to the gpu vessels


def reductions():
    out = []
    fs = json.loads((ROOT / "results" / "fleet" / "heldout" / "SUMMARY.json").read_text())
    for v, d in fs["vessels"].items():
        p = {x["metric"]: x for x in d["paired"]["omni_fleet_vs_k8s_hpa70_karpenter"]}["energy_kwh"]
        b = p["base"]
        out.append((v, "HPA 0.7 + Karpenter-lite", -p["ci95"][1] / b, -p["delta"] / b, -p["ci95"][0] / b))
    pl = json.loads((ROOT / "results" / "fleet" / "planetlab" / "SUMMARY.json").read_text())
    p = {x["metric"]: x for x in pl["paired"]["omni_fleet_vs_k8s_hpa70_karpenter"]}["energy_kwh"]
    b = pl["means"]["k8s_hpa70_karpenter"]["energy_kwh"]
    out.append(("planetlab_shapes", "HPA 0.7 + Karpenter-lite", -p["ci95"][1] / b, -p["delta"] / b, -p["ci95"][0] / b))
    return out


def python_reference(row):
    name, v, base, nodes, kw, pue, usd, co2, lo, mid, hi = row
    mwh = nodes * kw * pue * 8760.0 / 1000.0
    return [mwh] + [mwh * r for r in (lo, mid, hi)] + [mwh * 1000.0 * usd * r for r in (lo, mid, hi)] + [mwh * co2 * r for r in (lo, mid, hi)]


def main(exe=None, out_dir=ROOT / "results"):
    rows = [(pn, v, base, n, (GPU_NODE_KW if v.startswith("gpu") else kw), pue, usd, co2, lo, mid, hi)
            for (pn, n, kw, pue, usd, co2) in PROFILES for (v, base, lo, mid, hi) in reductions()]
    inp = Path(out_dir) / "SAVINGS_INPUTS.csv"
    with open(inp, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["profile", "vessel", "baseline", "nodes", "node_avg_kw", "pue", "usd_per_kwh", "kg_co2_per_kwh", "reduction_low", "reduction_mid", "reduction_high"])
        for r in rows: w.writerow([r[0], r[1], r[2]] + [repr(float(x)) for x in r[3:]])
    exe = exe or str(ROOT / "cpp" / "build" / "oc_savings")
    subprocess.run([exe, str(inp), str(Path(out_dir) / "SAVINGS.csv")], check=True)
    got = list(csv.DictReader(open(Path(out_dir) / "SAVINGS.csv")))
    keys = ["baseline_mwh_per_year", "saved_mwh_low", "saved_mwh_mid", "saved_mwh_high", "saved_usd_low", "saved_usd_mid", "saved_usd_high", "saved_tco2_low", "saved_tco2_mid", "saved_tco2_high"]
    worst = max(abs(float(g[k]) - ref) / max(1.0, abs(ref)) for g, r in zip(got, rows) for k, ref in zip(keys, python_reference(r)))
    assert worst < 1e-9, worst
    for g in got:
        print(f"{g['profile']:17s} {g['vessel']:16s} saved {float(g['saved_mwh_mid']):>12,.0f} MWh/yr  ${float(g['saved_usd_low']):>14,.0f} to ${float(g['saved_usd_high']):>14,.0f}  {float(g['saved_tco2_mid']):>10,.0f} tCO2")
    return got


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
