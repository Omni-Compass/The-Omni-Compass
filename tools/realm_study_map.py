# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Wave 3 of the realm study: map every row of the 656 catalog to the real controls found in waves 1 and 2.

  python3 tools/realm_study_map.py

For each muscle, the best-matching real control by shared words (name against control, setting and area), its score,
and a verdict filled in by hand where the words do not decide it (docs/realm_study/wave3_verdicts.csv). Writes
docs/realm_study/wave3_map.csv.
"""
import csv, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "docs" / "realm_study"
STOP = {"the", "of", "and", "a", "to", "per", "or", "policy", "control", "mode", "in", "on", "by", "for", "with"}


def toks(s):
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) > 1 and t not in STOP}


# each family is matched only against the areas of real controls it belongs to (then everything, if nothing fits)
FAMILY_AREAS = {
    "Work Admission & Demand Shaping": ["admission"], "Kubernetes Workload Scaling": ["k8s_workload"],
    "Container Resources": ["k8s_container", "cgroup"], "Kubernetes Placement & Scheduling": ["k8s_sched"],
    "Node Fleet & Karpenter-Class Control": ["nodes"], "OpenShift & Machine API": ["nodes"],
    "Cloud VM & Capacity": ["vm"], "Host CPU & Memory": ["cpu", "cgroup"], "NVIDIA GPU Hardware": ["gpu"],
    "GPU Fabric & RDMA": ["fabric"], "AI Inference Serving": ["inference"], "AI Training": ["training"],
    "HPC & Distributed Compute": ["hpc"], "Distributed Cluster Managers": ["clustermgr", "hpc"],
    "Cross-Cluster, Multi-Region & Edge": ["multiregion"], "Kubernetes Dynamic Device Allocation": ["dra"],
    "DPU SmartNIC & Programmable IO": ["dpu"], "Robotics Motion Control": ["robot_motion"],
    "Robotics Fleet & Warehouse Automation": ["robot_fleet"], "Aviation & Autonomous Flight": ["flight"],
    "Spacecraft & Flight Software": ["space"], "Automotive EV & Mobile Powertrain": ["ev"],
    "Quantum Computing Control Simulation": ["quantum"], "Industrial PLC & Process Automation": ["process"],
    "Energy Storage & Microgrid": ["storage_grid"], "PDU, UPS & Electrical Distribution": ["power"],
    "Cooling, Chillers & Thermodynamics": ["cooling"], "Facility & Grid Optimization": ["facility", "storage_grid"],
    "Grid Transmission & Distribution": ["grid"], "Semiconductor Fab & Precision Manufacturing": ["fab"],
    "Water Wastewater & Pumping": ["water"], "Building & Critical Environment HVAC": ["building"],
    "Network Routing & Switching": ["network"], "Service Mesh & API Reliability": ["mesh"],
    "Storage Block/File/Object": ["storage"], "Database & Transactions": ["database"],
    "Messaging & Streaming": ["messaging"], "Cache & Memory Services": ["cache"],
    "Search, Indexing & Vector DB": ["search"], "Data Analytics & ETL": ["analytics"],
    "Runtime & Application": ["runtime"], "Observability & Telemetry": ["observe"],
    "Reliability, Security & Recovery": ["protect"], "Commerce & Payment Systems": ["commerce"],
    "Workflow, Logistics & Fulfillment": ["workflow"], "Telecom RAN & Edge Radio": ["telecom"],
}


def controls():
    out = []
    for fn, realm in (("spine_wave1.csv", "spine"), ("realm1_compute_wave1.csv", "r1"), ("realm2_physics_wave1.csv", "r2"),
                      ("realm3_energy_wave1.csv", "r3"), ("realm4_distribution_wave1.csv", "r4")):
        for r in csv.DictReader((S / fn).open()):
            r["src_realm"] = realm
            out.append(r)
    for r in csv.DictReader((S / "wave2_industry_additions.csv").open()):
        r["src_realm"] = r["realm"]
        out.append(r)
    return out


def main():
    cat = list(csv.DictReader((ROOT / "realms" / "catalog.csv").open()))
    ctl = controls()
    verdicts = {}
    for name in ("wave3_verdicts.csv", "wave3_overrides.csv"):          # later files win
        vf = S / name
        if vf.exists():
            verdicts.update({r["muscle"]: r for r in csv.DictReader(vf.open())})
    by_name = {c["control"]: c for c in ctl}
    rows = []
    for m in cat:
        mt = toks(m["muscle"])
        pool = [c for c in ctl if c["area"] in FAMILY_AREAS.get(m["family"], [])] or ctl
        best = max(pool, key=lambda c: (len(mt & (toks(c["control"]) | toks(c["setting"]) | toks(c["area"]))), -len(c["control"])))
        bt = toks(best["control"]) | toks(best["setting"]) | toks(best["area"])
        score = len(mt & bt) / max(1, len(mt))
        v = verdicts.get(m["muscle"], {})
        if v.get("control"):
            best = by_name[v["control"]]
            bt = toks(best["control"]) | toks(best["setting"]) | toks(best["area"])
            score = len(mt & bt) / max(1, len(mt))
        elif "control" in v:                                          # hand verdict with no matching control
            best = {"control": "", "system": "", "setting": "", "source": ""}
        rows.append(dict(muscle_id=m["muscle_id"], family=m["family"], muscle=m["muscle"], realm=m["realm"],
                         best_control=best["control"], best_system=best["system"], best_setting=best["setting"],
                         source=best["source"], score=f"{score:.2f}",
                         verdict=v.get("verdict", "real" if score >= 0.5 else "review"),
                         note=v.get("note", "")))
    with (S / "wave3_map.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    from collections import Counter
    print(Counter(r["verdict"] for r in rows))
    return rows


if __name__ == "__main__":
    main()
