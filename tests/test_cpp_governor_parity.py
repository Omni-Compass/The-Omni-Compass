"""C++ governor (cpp/src/governor.cpp) vs Python governor (omnicompass/adapter.py) on recorded stack telemetry."""
import csv, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import benchmarks.stack_benchmark as B
from omnicompass import stack_sim as S
from omnicompass.adapter import Governor, AllocationLaw

def main(exe, n=60, mode="power_protect"):
    rows, exp = [], []
    class Rec(Governor):
        def step(self, obs, conflicts):
            o = {"q": obs.get("queue_ratio", 0.0), "load": obs.get("load_ratio", 0.0), "power": obs.get("power_stress", 0.0),
                 "thermal": obs.get("thermal", 0.0), "network": obs.get("network_stress", 0.0), "drift": obs.get("drift_ratio", 0.0),
                 "stale": obs.get("stale", 0.0), "security": obs.get("security_block", 0.0)}
            rows.append({"scenario_id": self._sid, "step": len([r for r in rows if r["scenario_id"] == self._sid]),
                         **o, "conflicts": conflicts, "current_cap": self.current_cap, "nodes": self.nodes})
            d = super().step(obs, conflicts)
            exp.append(d); return d
    cfg = S.ManagerBenchmarkConfig(profile="full", scenarios=n, steps=72)
    orig = B.Governor
    for s in S._mom_generate_scenarios(cfg, 424242)[:n]:
        class R(Rec): _sid = s.scenario_id
        B.Governor = R
        if mode.startswith("fleet"):
            from omnicompass.adapter import mode_law
            B.simulate(s, "omni_direct", cfg, mode_law(mode))
        else:
            B.simulate(s, "omni_k8s_throughput" if mode == "throughput" else "omni_direct", cfg, AllocationLaw())
    B.Governor = orig
    tmp = Path(tempfile.mkdtemp())
    with open(tmp / "obs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader()
        for r in rows: w.writerow({k: repr(v) if isinstance(v, float) else v for k, v in r.items()})
    subprocess.run([exe, str(tmp / "obs.csv"), str(tmp / "out.csv"), mode], check=True)
    got = list(csv.DictReader(open(tmp / "out.csv")))
    assert len(got) == len(exp)
    mx = 0.0; bad = 0
    for g, e in zip(got, exp):
        bad += int(int(g["node_delta"]) != e["node_delta"]) + int(bool(int(g["change_permitted"])) != e["change_permitted"])
        bad += int(bool(int(g["rollback_authorized"])) != e["rollback_authorized"]) + int(bool(int(g["route_shift"])) != e["route_shift"])
        for k, v in (("power_cap", e["power_cap"]), ("demand", e["demand"]), ("command", e["command"]),
                     *((k, e["state"][k]) for k in ("E", "U", "I_U", "S", "B"))):
            mx = max(mx, abs(float(g[k]) - v))
    print(f"C++ vs Python governor ({mode}): {len(exp)} directives, discrete mismatches = {bad}, max |diff| = {mx:.3e}")
    assert bad == 0 and mx < 1e-12
    print("PASS test_cpp_governor_parity")

if __name__ == "__main__":
    exe = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "cpp" / "build" / "oc_governor")
    for m_ in ("power_protect", "throughput", "fleet", "fleet_balanced", "fleet_wear"):
        main(exe, mode=m_)
