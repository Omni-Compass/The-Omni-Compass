"""Native benchmark arm vs the reference engine's fragmented-stack simulator."""
import importlib.util, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from benchmarks.stack_benchmark import simulate
from omnicompass import stack_sim as S
from omnicompass.adapter import AllocationLaw

def main(n=60):
    import shutil, tempfile
    ref = Path(tempfile.mkdtemp()) / "omni_compass_reference_engine.py"
    shutil.copy(ROOT / "reference" / "omni_compass_reference_engine.py", ref)
    spec = importlib.util.spec_from_file_location("oc_ref", ref)
    E = importlib.util.module_from_spec(spec); sys.modules["oc_ref"] = E; spec.loader.exec_module(E)
    cfg = S.ManagerBenchmarkConfig(profile="full", scenarios=n, steps=72)
    scns = S._mom_generate_scenarios(cfg, 224297269)[:n]
    ok = 0
    for s in scns:
        r = E._mom_simulate_policy(s, "fragmented_managers", cfg)[0]
        m = simulate(s, "native", cfg, AllocationLaw())
        same = all(abs(a - b) < 1e-9 for a, b in [(r.mean_queue_units, m["mean_queue"]), (r.facility_energy_kwh, m["energy_kwh"]),
                   (r.node_hours, m["node_hours"]), (r.completed_work_units / r.total_demand_units, m["availability"]),
                   (r.pages_total, m["pages"]), (r.manual_interventions, m["human_interventions"])])
        ok += same
    print(f"native arm vs reference engine simulator: {ok}/{n} identical")
    assert ok == n
    print("PASS test_native_equivalence")

if __name__ == "__main__":
    main()
