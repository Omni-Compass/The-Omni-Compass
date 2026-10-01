"""Build realms/catalog.csv: the 656-row muscle tower, each row given its realm, its plant, and the knob Omni may hold.

  python3 tools/realms_catalog.py CANONICAL_656_TOWER.csv

The tower itself (muscle id, family, name) comes unchanged from the XPASS package's canonical 656 list. This tool adds
four columns by the fixed rules below; the result is committed as data, so every row can be read and contested:

  realm     one of the four realms, by family
  template  the plant model the family runs on (realms/plants.py)
  preset    the family's parameter set for that plant (realms/presets.py)
  knob      the one knob Omni may hold for this muscle: capacity, setpoint, power or admission, from the muscle's name
            (first matching rule of its template, else capacity)
"""
import csv, hashlib, json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R1, R2, R3, R4 = "compute_ai_cloud", "physics_robotics_autonomous", "energy_facility_industrial", "distribution_specialized"

FAMILY = {
    "Work Admission & Demand Shaping": (R1, "compute_pool", "server"),
    "Kubernetes Workload Scaling": (R1, "compute_pool", "server"),
    "Container Resources": (R1, "compute_pool", "server"),
    "Kubernetes Placement & Scheduling": (R1, "compute_pool", "server"),
    "Node Fleet & Karpenter-Class Control": (R1, "compute_pool", "node"),
    "OpenShift & Machine API": (R1, "compute_pool", "node"),
    "Cloud VM & Capacity": (R1, "compute_pool", "node"),
    "Host CPU & Memory": (R1, "compute_pool", "cpu_host"),
    "NVIDIA GPU Hardware": (R1, "compute_pool", "gpu"),
    "GPU Fabric & RDMA": (R1, "compute_pool", "fabric"),
    "AI Inference Serving": (R1, "compute_pool", "gpu"),
    "AI Training": (R1, "compute_pool", "gpu_batch"),
    "HPC & Distributed Compute": (R1, "compute_pool", "batch"),
    "Distributed Cluster Managers": (R1, "compute_pool", "batch"),
    "Cross-Cluster, Multi-Region & Edge": (R1, "compute_pool", "node"),
    "Kubernetes Dynamic Device Allocation": (R1, "compute_pool", "gpu"),
    "DPU SmartNIC & Programmable IO": (R1, "compute_pool", "fabric"),
    "Robotics Motion Control": (R2, "motion_axis", "robot_joint"),
    "Robotics Fleet & Warehouse Automation": (R2, "compute_pool", "robot_fleet"),
    "Aviation & Autonomous Flight": (R2, "motion_axis", "flight_axis"),
    "Spacecraft & Flight Software": (R2, "motion_axis", "reaction_wheel"),
    "Automotive EV & Mobile Powertrain": (R2, "motion_axis", "ev_traction"),
    "Quantum Computing Control Simulation": (R2, "compute_pool", "qpu"),
    "Industrial PLC & Process Automation": (R3, "process_loop", "process"),
    "Energy Storage & Microgrid": (R3, "energy_storage", "microgrid"),
    "PDU, UPS & Electrical Distribution": (R3, "energy_storage", "ups"),
    "Cooling, Chillers & Thermodynamics": (R3, "thermal_zone", "data_hall"),
    "Facility & Grid Optimization": (R3, "energy_storage", "facility"),
    "Grid Transmission & Distribution": (R3, "process_loop", "feeder_voltage"),
    "Semiconductor Fab & Precision Manufacturing": (R3, "process_loop", "chamber"),
    "Water Wastewater & Pumping": (R3, "process_loop", "water"),
    "Building & Critical Environment HVAC": (R3, "thermal_zone", "building"),
    "Network Routing & Switching": (R4, "compute_pool", "network"),
    "Service Mesh & API Reliability": (R4, "compute_pool", "server"),
    "Storage Block/File/Object": (R4, "compute_pool", "storage"),
    "Database & Transactions": (R4, "compute_pool", "database"),
    "Messaging & Streaming": (R4, "compute_pool", "server"),
    "Cache & Memory Services": (R4, "compute_pool", "server"),
    "Search, Indexing & Vector DB": (R4, "compute_pool", "server"),
    "Data Analytics & ETL": (R4, "compute_pool", "batch"),
    "Runtime & Application": (R4, "compute_pool", "server"),
    "Observability & Telemetry": (R4, "compute_pool", "server"),
    "Reliability, Security & Recovery": (R4, "compute_pool", "server"),
    "Commerce & Payment Systems": (R4, "compute_pool", "commerce"),
    "Workflow, Logistics & Fulfillment": (R4, "compute_pool", "workflow"),
    "Telecom RAN & Edge Radio": (R4, "compute_pool", "ran"),
}

# knob rules per template, in order; the first match on the muscle's name wins, else "capacity"
KNOB = {
    "compute_pool": [
        ("admission", r"admission|admit|_gate|gate$|shed|backpressure|concurrency|burst|rate_limit|connection_limit|queue_limit"
                      r"|queue_depth|quota|priority|fair|preempt|backoff|retry|timeout|circuit|throttle|hold|pause|abort|freeze"
                      r"|isolat|quarantine|evict|drain|cordon|deadline|outlier|ejection|kill_switch|budget"),
        ("power", r"power|freq|clock|rapl|energy_perf|idle_policy|thermal|uncore|tx_power|precision|profile"),
        ("setpoint", r"target|threshold|_ttl$|ratio|fraction|weight|interval|window"),
    ],
    "motion_axis": [
        ("admission", r"admission|gate|hold|stop|quarantine|safe|failsafe|termination|land|return|mode|reserve|geofence"
                      r"|isolation|watchdog|fault|recovery|transition|schedule"),
        ("power", r"effort|force|torque|power|current|thrust|throttle|rcs|brak|regen|charge|discharge|thermal|duty|voltage"
                  r"|budget|limit"),
    ],
    "thermal_zone": [
        ("admission", r"shed|migrate|emergency|mode|occupancy"),
        ("power", r"power|budget|demand_limit|compressor_authority"),
        ("setpoint", r"temperature|setpoint|target|envelope|humidity"),
    ],
    "energy_storage": [
        ("admission", r"shed|admission|response|flex|transfer|isolation|trip|islanding|emergency|price_gate|carbon"),
        ("setpoint", r"reserve|soc|target|pue|schedule|time_of_use"),
        ("power", r"power|charge|discharge|limit|cap|rate|curtail|budget|allocation"),
    ],
    "process_loop": [
        ("admission", r"admission|shed|shutdown|isolation|purge|backwash|protection|restoration|quarantine|dispatch"
                      r"|priority|selection|authority"),
        ("setpoint", r"setpoint|target|level|pressure|temperature|voltage|tap|droop|position"),
        ("power", r"power|heater|dose|aeration|rf_"),
    ],
}


# names the rules above would place wrongly, set by hand
OVERRIDE = {"node_power_on": "capacity", "erasure_code_profile": "capacity", "thermal_throttle_policy": "power",
            "energy_recovery_target": "power", "microgrid_emergency_reserve": "setpoint", "jerk_limit": "capacity"}


def knob_for(template, name):
    if name in OVERRIDE:
        return OVERRIDE[name]
    for knob, pattern in KNOB[template]:
        if re.search(pattern, name):
            return knob
    return "capacity"


def main(argv):
    src = Path(argv[1])
    rows = list(csv.DictReader(src.open()))
    assert len(rows) == 656, len(rows)
    out = []
    for r in rows:
        realm, template, preset = FAMILY[r["family"]]
        out.append(dict(muscle_id=r["muscle_id"], family_id=r["family_id"], family=r["family"], muscle=r["canonical_name"],
                        realm=realm, template=template, preset=preset, knob=knob_for(template, r["canonical_name"])))
    out.sort(key=lambda x: (x["realm"], x["family"], x["muscle_id"].zfill(12)))
    with (ROOT / "realms" / "catalog.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    prov = {"source": "organism/referee_canonical_v3/CANONICAL_656_TOWER.csv (XPASS27_FOUR_PLANTS package)",
            "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "rows": len(out),
            "added_columns": "realm, template, preset, knob: tools/realms_catalog.py"}
    (ROOT / "realms" / "catalog_provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
    print(Counter(x["realm"] for x in out))
    print(Counter((x["template"], x["knob"]) for x in out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
