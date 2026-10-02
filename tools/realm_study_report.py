# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Wave 3 result: the true muscle list per realm, from the 656 catalog checked against the real controls.

  python3 tools/realm_study_report.py

Keeps every catalog row that is a real control (one row per real control: duplicates fold into the first), adds the real
controls the catalog does not have, sets aside protective actions and non-controls, and writes
docs/realm_study/TRUE_MUSCLES.csv and docs/realm_study/WAVE3_REPORT.md.
"""
import csv
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "docs" / "realm_study"
SRC = (("spine_wave1.csv", "spine"), ("realm1_compute_wave1.csv", "compute_ai_cloud"),
       ("realm2_physics_wave1.csv", "physics_robotics_autonomous"), ("realm3_energy_wave1.csv", "energy_facility_industrial"),
       ("realm4_distribution_wave1.csv", "distribution_specialized"))
W2 = {"spine": "spine", "r1": "compute_ai_cloud", "r2": "physics_robotics_autonomous", "r3": "energy_facility_industrial",
      "r4": "distribution_specialized"}
NAMES = {"spine": "Shared spine (all four realms)", "compute_ai_cloud": "Compute / AI / Cloud",
         "physics_robotics_autonomous": "Physics / Robotics / Autonomous",
         "energy_facility_industrial": "Energy / Facility / Industrial", "distribution_specialized": "Distribution / Specialized"}


def main():
    ctl = OrderedDict()
    for fn, realm in SRC:
        for c in csv.DictReader((S / fn).open()):
            ctl.setdefault(c["control"], dict(c, home=realm))
    for c in csv.DictReader((S / "wave2_industry_additions.csv").open()):
        ctl.setdefault(c["control"], dict(c, home=W2[c["realm"]]))
    cat = {r["muscle_id"]: r for r in csv.DictReader((ROOT / "realms" / "catalog.csv").open())}
    mp = list(csv.DictReader((S / "wave3_map.csv").open()))
    keep, used, aside = [], set(), []
    for m in mp:
        home = "spine" if len(cat[m["muscle_id"]]["realms"].split(";")) == 4 else m["realm"]
        v = m["verdict"]
        if v in ("protective", "not-a-control", "duplicate"):
            aside.append(dict(muscle=m["muscle"], family=m["family"], verdict=v, note=m["note"]))
            continue
        key = m["best_control"] or ("new:" + m["muscle"])
        if v in ("real", "real-app", "real-config") and key in used:
            aside.append(dict(muscle=m["muscle"], family=m["family"], verdict="duplicate",
                              note=f"same real control as another catalog muscle: {key}"))
            continue
        used.add(key)
        c = ctl.get(m["best_control"], {})
        keep.append(dict(muscle=m["muscle"], realm=home, family=m["family"], origin="catalog", verdict=v,
                         control=m["best_control"] or m["note"], system=c.get("system", ""),
                         setting=c.get("setting", "") or m["note"], source=c.get("source", "")))
    for name, c in ctl.items():
        if name in used:
            continue
        keep.append(dict(muscle=name.replace(" ", "_").replace("/", "").replace("(", "").replace(")", ""),
                         realm=c["home"], family=c.get("area", ""), origin="added (real, not in the 656)",
                         verdict="real", control=name, system=c["system"], setting=c["setting"], source=c["source"]))
    with (S / "TRUE_MUSCLES.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(keep[0])); w.writeheader(); w.writerows(keep)
    with (S / "SET_ASIDE.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(aside[0])); w.writeheader(); w.writerows(aside)
    v = Counter(m["verdict"] for m in mp)
    by = Counter(k["realm"] for k in keep)
    cat_by = Counter(k["realm"] for k in keep if k["origin"] == "catalog")
    add_by = Counter(k["realm"] for k in keep if k["origin"] != "catalog")
    L = ["# Realm study, wave 3: the 656 checked against the real systems", "",
         "Waves 1 and 2 listed the real controls of each realm from the systems' own documentation (Kubernetes, Linux, "
         "NVIDIA, the clouds, ROS 2, PX4, BACnet, IEEE 1547 / 2030.5, IEC 61850, SEMI, PostgreSQL, Kafka, Redis, "
         "Envoy, O-RAN and others) and from what Meta, Google, Microsoft, Intel, NVIDIA, Netflix and Uber publish about "
         "production. Wave 3 checks every catalog row against them (`wave3_map.csv`, hand verdicts in "
         "`wave3_verdicts.csv` and `wave3_overrides.csv`).", "",
         "## The 656, row by row", "",
         "| Verdict | Rows | Meaning |", "|---|---:|---|",
         f"| real | {v['real']} | a real control, named with its setting and source |",
         f"| real, application level | {v['real-app']} | real, but set in the application rather than a platform |",
         f"| real, configuration only | {v['real-config']} | real, but configured once, not moved at run time |",
         f"| real, missing from waves 1-2 | {v['missing-added']} | real; added to the list of controls |",
         f"| duplicate | {v['duplicate']} | the same control as another catalog row |",
         f"| protective | {v['protective']} | a safety action owned by a safety system; never for an optimiser |",
         f"| not a control | {v['not-a-control']} | moves no setting (an objective, an alert, or not settable) |", "",
         f"After folding duplicates (including rows that point at the same real control), **{len([k for k in keep if k['origin']=='catalog'])}** "
         "catalog rows are distinct real controls. Some of that folding is by mechanism, not by loop: the furnace, pressure, "
         "temperature and level setpoints all fold into one \"PID setpoint\" control. On a real plant each loop is its "
         "own muscle, so 448 is a floor for distinct controls, not a ceiling.", "",
         "## Real controls the 656 does not have", "",
         f"**{len(keep) - len([k for k in keep if k['origin']=='catalog'])}** real controls from waves 1 and 2 are not in "
         "the catalog, among them the HPA's own behaviour settings (stabilisation windows, rate policies, tolerance), the "
         "Cluster Autoscaler's scale-down settings, CPU governor and turbo, NVIDIA application clocks and sync boost, "
         "IEEE 1547 volt-var and volt-watt, Guideline 36 trim-and-respond, PostgreSQL and InnoDB resource settings, and the "
         "production power-capping practices (hierarchical budgets, priority-aware capping, core packing). They are added.", "",
         "## The true muscle list, by realm", "",
         "| Realm | From the 656 | Added | True total |", "|---|---:|---:|---:|"]
    for k in NAMES:
        L.append(f"| {NAMES[k]} | {cat_by[k]} | {add_by[k]} | **{by[k]}** |")
    L += [f"| **All** | **{sum(cat_by.values())}** | **{sum(add_by.values())}** | **{len(keep)}** |", "",
          "Each realm's organism is its own row plus the shared spine. Every row of `TRUE_MUSCLES.csv` names the real "
          "control, its system, its exact setting and its source; `SET_ASIDE.csv` lists every catalog row not kept, "
          "with the reason.", "",
          "## What this does not claim", "",
          "- **This is not every setting that exists.** Linux alone has thousands. The list is the controls that change a "
          "system's energy, capacity or service and that a supervisory governor could hold, as the systems document them.",
          "- **The verdicts are hand judgements on documented controls**, made row by row and each one written down, so "
          "any of them can be contested.",
          "- **The realm harness still runs on the 656 catalog (round 3).** Moving it onto this list is a new round, with "
          "its own preregistration."]
    (S / "WAVE3_REPORT.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[L.index("## The true muscle list, by realm"):L.index("## The true muscle list, by realm") + 9]))


if __name__ == "__main__":
    main()
