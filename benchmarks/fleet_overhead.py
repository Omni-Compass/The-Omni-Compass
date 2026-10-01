"""Fleet overhead of infrastructure components under the keep-or-remove rule."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from omnicompass.muscles import Fleet, fleet_report

def main(out=ROOT / "results" / "fleet_overhead.json"):
    res = {}
    for util in (0.08, 0.30):
        for mesh in ("sidecar", "ambient"):
            res[f"util{int(util*100)}_{mesh}"] = fleet_report(Fleet(mean_cpu_utilization=util, mesh=mesh))
    Path(out).write_text(json.dumps(res, indent=2))
    r = res["util8_sidecar"]
    print(f"fleet: {r['fleet']['nodes']:,} nodes, {r['clusters']} clusters, {r['fleet_vcpu']:,} vCPU, {r['fleet_mwh_per_year']:,.0f} MWh/yr (util 8%)")
    for c in r["components"]:
        print(f"  {c['name'][:46]:46s} {c['role']:13s} {c['status']:10s} vCPU {c['vcpu']:>10,.0f} ({100*c['share_of_fleet_vcpu']:5.2f}%)  energy {100*c['share_of_fleet_energy_low']:5.2f}-{100*c['share_of_fleet_energy_high']:5.2f}%")
    for k, v in res.items():
        print(k, {role: f"{100*g['share_of_fleet_vcpu']:.2f}% vCPU, {100*g['share_of_fleet_energy_low']:.2f}-{100*g['share_of_fleet_energy_high']:.2f}% energy" for role, g in v["by_role"].items()},
              f"| idle vCPU {100*v['idle_share_of_fleet_vcpu']:.0f}% of fleet, idle draw {100*v['idle_vcpu_share_of_fleet_energy']:.0f}% of energy")

if __name__ == "__main__":
    main()
