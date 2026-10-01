"""Infrastructure component catalog and fleet overhead model.

Each component records its role, deployment pattern, resource footprint, the source of that
footprint and its evidence status, and its classification under the keep-or-remove rule:

  decision       control logic whose function the governor performs      -> candidate for removal
  observability  telemetry and storage for humans, audit and control     -> retained; control path replaced by direct sensing
  execution      machinery that performs the work                        -> retained
  security       cryptography, identity, policy, runtime detection       -> retained unless a stronger guarantee is proven

Evidence status:
  measured       benchmark or production measurement published by the source
  documented     formula or default published in official documentation
  example        request values from a published example manifest
  assumption     modelling assumption; parameter exposed for sensitivity analysis

Energy per resource follows the Cloud Carbon Footprint method:
  W = vCPU * (W_min + u * (W_max - W_min)) + GB * W_mem, scaled by PUE.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List

W_MIN_PER_VCPU = 0.434
W_MAX_PER_VCPU = 1.948
W_PER_GB = 0.392
ENERGY_SOURCE = ("Cloud Carbon Footprint coefficients (SPECpower-derived), AMD EPYC 3rd generation: "
                 "0.434 W min, 1.948 W max per vCPU; memory 0.392 W per GB (arXiv 2510.26413)")


@dataclass(frozen=True)
class Component:
    name: str
    role: str
    scope: str
    vcpu: float
    gib: float
    status: str
    source: str
    verdict: str
    note: str = ""


def kube_reserved_cpu(cores: int) -> float:
    """AKS kube-reserved CPU table (Microsoft Learn), cores -> vCPU, linear between table points."""
    pts = [(1, 0.060), (2, 0.100), (4, 0.140), (8, 0.180), (16, 0.260), (32, 0.420), (64, 0.740)]
    if cores <= 1:
        return pts[0][1]
    for (c0, v0), (c1, v1) in zip(pts, pts[1:]):
        if cores <= c1:
            return v0 + (v1 - v0) * (cores - c0) / (c1 - c0)
    c0, v0 = pts[-2]; c1, v1 = pts[-1]
    return v1 + (v1 - v0) * (cores - c1) / (c1 - c0)


@dataclass
class Fleet:
    nodes: int = 100_000
    nodes_per_cluster: int = 5_000
    cores_per_node: int = 64
    gib_per_node: int = 256
    pods_per_node: int = 30
    series_per_node: int = 2_000
    long_term_replication: int = 3
    mean_cpu_utilization: float = 0.30
    pue: float = 1.18
    mesh: str = "sidecar"

    @property
    def clusters(self) -> int:
        return -(-self.nodes // self.nodes_per_cluster)


def catalog(f: Fleet) -> List[Component]:
    series = f.nodes * f.series_per_node
    C = []
    C.append(Component("kubelet + container runtime (kube-reserved)", "execution", "per node",
                       kube_reserved_cpu(f.cores_per_node) * f.nodes, 0.0, "documented",
                       "Microsoft Learn, AKS node resource reservations (CPU table)", "retain",
                       "memory reservation not counted here"))
    C.append(Component("node-exporter (metrics agent)", "observability", "per node", 0.050 * f.nodes,
                       100 / 1024 * f.nodes, "example", "OneUptime DaemonSet resource example (requests 50m / 100Mi)",
                       "retain for humans; control path replaced by direct sensing"))
    C.append(Component("log collector (Fluentd / Fluent Bit)", "observability", "per node", 0.100 * f.nodes,
                       200 / 1024 * f.nodes, "example", "OneUptime DaemonSet resource example (requests 100m / 200Mi)",
                       "retain for audit and humans"))
    C.append(Component("OpenTelemetry agent collector", "observability", "per node", 0.100 * f.nodes,
                       128 / 1024 * f.nodes, "example", "OneUptime agent-gateway topology (requests 100m / 128Mi)",
                       "retain for humans; control path replaced by direct sensing"))
    if f.mesh == "sidecar":
        C.append(Component("service-mesh sidecar proxies (Envoy, per pod)", "security", "per pod",
                           0.20 * f.pods_per_node * f.nodes, 60 / 1024 * f.pods_per_node * f.nodes, "measured",
                           "Istio 1.24 benchmark at 1,000 req/s, 1 KB: ~0.20 vCPU, ~60 MB per sidecar",
                           "retain (mTLS); independent option: ambient mode",
                           "load-dependent; an idle sidecar measured ~8 millicores / 40 Mi (Defense Unicorns)"))
    else:
        C.append(Component("service-mesh ztunnel (ambient, per node)", "security", "per node",
                           0.06 * f.nodes, 12 / 1024 * f.nodes, "measured",
                           "Istio 1.24 benchmark: ztunnel ~0.06 vCPU, ~12 MB", "retain (mTLS)"))
    C.append(Component("Prometheus (in-cluster head series)", "observability", "per cluster",
                       0.0, 3.0e-6 * series, "measured", "Robust Perception: ~3 kB per head series (Prometheus 2.20+)",
                       "retain for humans; control scrape load removable", "series_per_node is an assumption"))
    C.append(Component("long-term metrics (Mimir ingesters)", "observability", "fleet",
                       series * f.long_term_replication / 300_000, 2.5 * series * f.long_term_replication / 300_000,
                       "documented", "Grafana Mimir capacity planning: 1 core and 2.5 GB per 300,000 in-memory series",
                       "retain for audit"))
    C.append(Component("cluster autoscaler / Karpenter", "decision", "per cluster", 1.0 * f.clusters,
                       1.0 * f.clusters, "assumption", "typical controller sizing; not measured here",
                       "remove: governor owns capacity"))
    C.append(Component("HPA / VPA / KEDA controllers", "decision", "per cluster", 0.5 * f.clusters,
                       1.0 * f.clusters, "assumption", "typical controller sizing; not measured here",
                       "remove: governor owns replicas and sizing"))
    C.append(Component("power / thermal policy agents", "decision", "per node", 0.010 * f.nodes,
                       32 / 1024 * f.nodes, "assumption", "typical node agent sizing; not measured here",
                       "remove: governor owns power caps"))
    C.append(Component("alert routing and paging (Alertmanager)", "decision", "per cluster", 0.2 * f.clusters,
                       0.5 * f.clusters, "assumption", "sizing scales with firing alerts (Grafana Mimir guidance)",
                       "remove paging path; keep audit notifications"))
    C.append(Component("Terraform as live capacity controller", "decision", "fleet", 0.0, 0.0, "assumption",
                       "run cost negligible; harm is stale overwrites (measured in the stack benchmark)",
                       "remove from the live control path; retain as audit record"))
    return C


def watts(vcpu: float, gib: float, u: float, pue: float) -> float:
    return pue * (vcpu * (W_MIN_PER_VCPU + u * (W_MAX_PER_VCPU - W_MIN_PER_VCPU)) + gib * 1.073741824 * W_PER_GB)


def fleet_report(f: Fleet) -> Dict:
    comps = catalog(f)
    total_vcpu = f.nodes * f.cores_per_node
    total_gib = f.nodes * f.gib_per_node
    fleet_w = watts(total_vcpu, total_gib, f.mean_cpu_utilization, f.pue)
    rows = []
    for c in comps:
        lo, hi = watts(c.vcpu, c.gib, 0.0, f.pue), watts(c.vcpu, c.gib, 1.0, f.pue)
        rows.append({**asdict(c), "watts_low": lo, "watts_high": hi,
                     "mwh_per_year_low": lo * 8760 / 1e6, "mwh_per_year_high": hi * 8760 / 1e6,
                     "share_of_fleet_vcpu": c.vcpu / total_vcpu,
                     "share_of_fleet_energy_low": lo / fleet_w, "share_of_fleet_energy_high": hi / fleet_w})
    by_role = {}
    for r in rows:
        g = by_role.setdefault(r["role"], {"vcpu": 0.0, "share_of_fleet_vcpu": 0.0,
                                            "share_of_fleet_energy_low": 0.0, "share_of_fleet_energy_high": 0.0,
                                            "mwh_per_year_low": 0.0, "mwh_per_year_high": 0.0})
        for k in g:
            g[k] += r[k]
    idle_vcpu = total_vcpu * (1.0 - f.mean_cpu_utilization)
    idle_w = f.pue * idle_vcpu * W_MIN_PER_VCPU
    return {"fleet": asdict(f), "clusters": f.clusters, "fleet_vcpu": total_vcpu, "fleet_mwh_per_year": fleet_w * 8760 / 1e6,
            "energy_model": ENERGY_SOURCE, "components": rows, "by_role": by_role,
            "idle_vcpu": idle_vcpu, "idle_share_of_fleet_vcpu": 1.0 - f.mean_cpu_utilization,
            "idle_vcpu_share_of_fleet_energy": idle_w / fleet_w}
