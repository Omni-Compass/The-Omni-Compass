#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""The catalog of the 656 muscles, explained: what each is for, what Omni-Compass reads and writes on it, how it is
wired, and which organisms it belongs to. Read from realms/catalog.csv; writes docs/MUSCLE_CATALOG.md.

    python3 tools/muscle_catalog.py
"""
from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "MUSCLE_CATALOG.md"
REALMS = OrderedDict([("compute_ai_cloud", "Compute / AI / Cloud"), ("physics_robotics_autonomous", "Physics / Robotics / Autonomous"),
                      ("energy_facility_industrial", "Energy / Facility / Industrial"), ("distribution_specialized", "Distribution / Specialized")])
BANNER = ("> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not "
          "open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, "
          "commercialization, monetization, production use, redistribution, hosted service or incorporation into a product "
          "requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Patent applications, "
          "copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its "
          "software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).")

# the plant each muscle is modelled on (realms/plants.py): what it is, what its service reading is, what its lever does
TEMPLATE = {
    "compute_pool": ("a pool of servers, pods, GPUs, links or disks serving a stream of requests or jobs",
                     "how far its queue and its load sit toward the service line (queue or lateness, and load above half)",
                     "the capacity it may use: its replica or instance count (through its autoscaler's target or floor), its power share, or one unit given back through the release gate"),
    "thermal_zone": ("a data hall or building zone cooled by chillers, air handlers or fans",
                     "its temperature against its limit",
                     "its supply setpoint (colder is more cooling), its power share, or one cooling unit given back when the room has margin"),
    "energy_storage": ("a battery, UPS or microgrid store with a load and a grid connection",
                       "its draw on the grid connection and its reserve",
                       "its reserve setpoint (how much charge it holds back); its power limit is left native"),
    "motion_axis": ("a motor-driven axis: a robot joint, a flight-control surface, a reaction wheel, a traction motor",
                    "its tracking error and its load",
                    "its speed and effort share, or its power share"),
    "process_loop": ("a regulated process: a temperature, pressure, flow, level, voltage or composition held at a setpoint",
                     "how far the process sits from its band",
                     "its setpoint within its safe band, its actuator range, or its power share"),
}
KNOB = {
    "capacity": "**capacity**: how much of the machine is in service (replicas, instances, units, speed). Omni-Compass writes it.",
    "admission": "**admission**: what is let in (queues, rate limits, admission control). Omni-Compass reads it and leaves it to its own controller in the current law; it is counted, never written.",
    "power": "**power**: the power share or limit the machine may draw. Omni-Compass writes it inside its cover.",
    "setpoint": "**setpoint**: the target the machine's own loop holds (a temperature, a reserve, a process value). Omni-Compass moves it inside its safe band.",
}
# the class of machine each preset stands for (realms/presets.py), and how such a muscle is reached in a real stack
PRESET = {
    "server": ("an application service on servers or pods", "the Kubernetes API (HPA target and floor, pod resize)"),
    "node": ("a fleet of machines or VMs that boot in minutes", "the node pool's size command (Karpenter, Cluster Autoscaler, MachineSet, cloud ASG)"),
    "cpu_host": ("a CPU host whose clock and power can be set", "Linux cpufreq and RAPL"),
    "gpu": ("GPU serving with a response-time target", "nvidia-smi (clock ceiling and power limit) or the serving autoscaler"),
    "gpu_batch": ("GPU training and batch work", "nvidia-smi, the job scheduler's pause and resume"),
    "batch": ("batch and queued jobs", "the job queue (Kubernetes Jobs, Slurm, Spark)"),
    "fabric": ("a high-speed fabric (RDMA, DPU, SmartNIC)", "the fabric manager's API"),
    "robot_fleet": ("a fleet of robots or vehicles taking tasks", "the fleet manager's dispatch API"),
    "qpu": ("a quantum or specialised accelerator queue", "the accelerator's job queue"),
    "network": ("network routing and switching", "the network controller (SDN, routing API)"),
    "storage": ("block, file or object storage", "the storage system's QoS and tiering API"),
    "database": ("a database cluster", "the database operator (replicas, connection pools)"),
    "commerce": ("a customer-facing service with bursts", "the Kubernetes API"),
    "workflow": ("a workflow or pipeline engine", "the workflow engine's concurrency settings"),
    "ran": ("a radio access network cell or site", "the RAN controller (O-RAN interfaces)"),
    "data_hall": ("a data hall cooling plant", "the building management system (BACnet, Modbus) or its command line"),
    "building": ("a building zone", "the building management system"),
    "microgrid": ("a microgrid battery and loads", "the inverter or energy management system (IEEE 2030.5, SunSpec, OpenADR)"),
    "ups": ("an uninterruptible power supply", "the UPS and PDU management interface (SNMP, Modbus)"),
    "facility": ("a facility battery behind the meter", "the energy management system"),
    "robot_joint": ("a robot joint servo", "the robot controller (ROS 2, EtherCAT, the drive's fieldbus)"),
    "flight_axis": ("a flight-control axis", "the flight controller (modelled only)"),
    "reaction_wheel": ("a spacecraft reaction wheel", "the attitude controller (modelled only)"),
    "ev_traction": ("an electric vehicle traction motor", "the vehicle's motor controller (CAN; modelled only)"),
    "process": ("an industrial process loop", "the PLC or DCS (OPC UA, EtherNet/IP, PROFINET)"),
    "water": ("a water or pumping process", "the SCADA system (Modbus, DNP3)"),
    "chamber": ("a controlled chamber (clean room, kiln, reactor)", "the PLC or DCS"),
    "feeder_voltage": ("a distribution feeder's voltage", "the distribution management system (IEC 61850, DNP3; modelled only)"),
}


def nice(m):
    return m.replace("_", " ")


def main():
    rows = list(csv.DictReader(open(ROOT / "realms" / "catalog.csv", encoding="utf-8")))
    spine = [r for r in rows if len(r["realms"].split(";")) == 4]
    counts = {k: sum(1 for r in rows if k in r["realms"].split(";")) for k in REALMS}
    L = ["# The 656 Muscles: What Each Is For, and How It Is Wired", "", BANNER, "",
         "A **muscle** is one setting on one machine that already has its own control: a replica target, a node pool's size, "
         "a GPU's clock ceiling, a chiller's setpoint, a battery's reserve, a joint's effort. Omni-Compass does not replace "
         "that control. It reads the machine's meters, computes one bounded force with the bowl law, and moves the setting "
         "the machine already accepts, through a plug that reads the setting once before the first write, reads back every "
         "write, steps aside if another controller moves it, and puts it back at the end.", "",
         "This chapter lists all 656 muscles of the catalog (`realms/catalog.csv`). For each one it says what kind of machine "
         "it is, which of the four kinds of knob it is, what Omni-Compass reads and does with it, how such a muscle is "
         "reached in a real stack, and which organisms it belongs to. The plants behind the benchmark numbers are models of "
         "these machines (evidence class **S**); a muscle in this list is wired on a real system only through the levels "
         "and the checks of the manual (chapters 8 and 9). See `DISCLOSURES.md`.", "",
         "## How to read an entry", "",
         "**The four kinds of knob.**", ""] + [f"- {v}" for v in KNOB.values()] + ["",
         "**The five kinds of plant.** Every muscle is modelled on one of five plants, each with its own service reading and "
         "lever:", "", "| Plant | What it is | What Omni-Compass reads | What Omni-Compass moves |", "|---|---|---|---|"]
    for k, (what, reads, moves) in TEMPLATE.items():
        L.append(f"| `{k}` | {what} | {reads} | {moves} |")
    L += ["", "**The organisms.** The 656 muscles build six organisms: each of the four realms (every muscle whose realm list "
          "includes it), the four stacked with every duplicate kept (1,226), and the whole tower with every muscle once (656). "
          "A muscle of the shared spine sits in all four realms.", "",
          "| Organism | Muscles |", "|---|---:|"]
    for k, n in REALMS.items():
        L.append(f"| {n} | {counts[k]} |")
    L += [f"| The four stacked, every duplicate kept | {sum(counts.values()):,} |", f"| The whole tower, every muscle once | {len(rows)} |", "",
          "**How a muscle is reached in a real stack.** The class of machine decides the wire:", "",
          "| Class of machine | What it is | The wire in a real stack |", "|---|---|---|"]
    for k in sorted({r["preset"] for r in rows}):
        what, wire = PRESET.get(k, (k, "see the manual, section 8.2"))
        L.append(f"| `{k}` | {what} | {wire} |")
    L += ["", "Wires marked *modelled only* exist as plants in the benchmark and are not built for live use.", ""]

    def family_tables(group, home_note):
        fams = OrderedDict()
        for r in group:
            fams.setdefault(r["family"], []).append(r)
        out = []
        for fam, rs in fams.items():
            t, p = rs[0]["template"], rs[0]["preset"]
            what = TEMPLATE[t][0]
            pw = PRESET.get(p, (p, "see the manual"))
            out += [f"### {fam} ({len(rs)} muscles)", "",
                    f"Each is {what}; its class is `{p}` ({pw[0]}), reached through {pw[1]}. Omni-Compass reads "
                    f"{TEMPLATE[t][1]}. {home_note}", "",
                    "| # | Muscle | Knob | What Omni-Compass does with it | Organisms |", "|---:|---|---|---|---|"]
            for r in sorted(rs, key=lambda r: (not r["muscle_id"].isdigit(), int("".join(c for c in r["muscle_id"] if c.isdigit()) or 0))):
                k = r["knob"]
                does = {"capacity": "holds it so the service sits in the middle of its band; more at once past the wall; gives back one unit at a time through the release gate",
                        "admission": "reads it; left to its own controller",
                        "power": "holds the power share inside its cover; full at once past the wall",
                        "setpoint": "moves the setpoint inside its safe band toward the calm end while the service has room; back toward stress at once when it does not"}[k]
                org = "all four realms" if len(r["realms"].split(";")) == 4 else ", ".join(REALMS[x].split(" / ")[0] for x in r["realms"].split(";"))
                out.append(f"| {r['muscle_id']} | {nice(r['muscle'])} | {k} | {does} | {org}; stack; tower |")
            out.append("")
        return out

    L += [f"## The shared spine: {len(spine)} muscles in all four realms", "",
          "The machines every realm stands on: servers, machines, GPUs and CPUs, network, storage, observability, security, "
          "cooling and electrical distribution. Each spine muscle is part of every realm's organism, counted once in the "
          "tower and four times in the stack.", ""]
    L += family_tables(spine, "It belongs to every organism.")
    for k, n in REALMS.items():
        own = [r for r in rows if r["realm"] == k and len(r["realms"].split(";")) < 4]
        L += [f"## Realm: {n} ({len(own)} muscles of its own, {counts[k]} in its organism with the spine)", ""]
        L += family_tables(own, f"Its home realm is {n}.")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(OUT, len(rows), "muscles")


if __name__ == "__main__":
    main()
