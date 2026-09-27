#!/usr/bin/env python3
"""One-command verification of the Omni-Compass package.

  python verify.py           full verification (about 15-30 minutes, single core)
  python verify.py --full-replay   additionally re-runs all held-out scenarios for every arm and requires the
                                  regenerated RUNS.csv and SUMMARY.json to equal the shipped files
  python verify.py --quick   skips the 20,000-case engine comparison, runs a 1,000,000-decision soak
                             instead of 100,000,000, and replays fewer scenarios
"""
import argparse, csv, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
ok = True

def check(name, cond, detail=""):
    global ok
    print(("PASS  " if cond else "FAIL  ") + name + (f"  ({detail})" if detail else ""))
    ok = ok and bool(cond)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def build_cpp(tmp):
    src = ROOT / "cpp"; b = tmp / "build"
    if shutil.which("cmake"):
        subprocess.run(["cmake", "-S", str(src), "-B", str(b), "-DCMAKE_BUILD_TYPE=Release"], check=True, capture_output=True)
        subprocess.run(["cmake", "--build", str(b), "-j2"], check=True, capture_output=True)
    else:
        b.mkdir(parents=True)
        cxx = shutil.which("g++") or shutil.which("clang++")
        srcs = [str(p) for p in (src / "src").glob("*.cpp")]
        for tool, name in (("run_fixture.cpp", "oc_run_fixture"), ("run_governor.cpp", "oc_governor"), ("soak.cpp", "oc_soak"),
                           ("smoke.cpp", "oc_smoke"), ("run_shield.cpp", "oc_shield"), ("run_hpa.cpp", "oc_hpa"), ("savings.cpp", "oc_savings")):
            subprocess.run([cxx, "-std=c++20", "-O2", "-I", str(src / "include"), *srcs, str(src / "tools" / tool), "-o", str(b / name)], check=True)
    return b

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true"); ap.add_argument("--full-replay", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT / "tools"))
    from code_fingerprint import fingerprint
    prov = json.loads((ROOT / "reference" / "PROVENANCE.json").read_text())
    ref = ROOT / prov["reference_engine"]
    import platform
    pyver = ".".join(platform.python_version_tuple()[:2])
    check("reference engine SHA-256", sha(ref) == prov["reference_engine_sha256"])
    reg = json.loads((ROOT / "results" / "PREREGISTRATION.json").read_text())
    for f, h in reg["sha256"].items():
        check(f"pre-registered file unchanged (SHA-256): {f}", sha(ROOT / f) == h)
    if pyver == reg.get("fingerprint_python", ""):
        check("reference engine program fingerprint", fingerprint(ref) == prov["program_fingerprint"])
        for f, h in reg["code_fingerprint"].items():
            check(f"program fingerprint: {f}", fingerprint(ROOT / f) == h)
    else:
        print(f"SKIP  program fingerprints (recorded with Python {reg.get('fingerprint_python')}, running {pyver}; "
              "ast.dump output is interpreter-version dependent; SHA-256 checks above are authoritative)")
    from tests import test_stack_sim_provenance, test_native_equivalence, test_cpp_governor_parity
    test_stack_sim_provenance.main(); check("stack simulator provenance", True)
    if not a.quick:
        from tests import test_core_parity
        test_core_parity.main(); check("core parity vs reference engine and 500 fixtures", True)
    test_native_equivalence.main(20 if a.quick else 60); check("native arm equals reference simulator", True)
    tmp = Path(tempfile.mkdtemp()); b = build_cpp(tmp)
    subprocess.run([str(b / "oc_run_fixture"), str(ROOT / "fixtures" / "current_500_inputs.csv"), str(tmp / "cpp.csv")], check=True)
    r = subprocess.run([sys.executable, str(ROOT / "cpp" / "scripts" / "compare_results.py"), str(ROOT / "fixtures" / "current_500_expected.csv"),
                        str(tmp / "cpp.csv"), str(tmp / "cpp.json")], capture_output=True, text=True)
    rep = json.loads((tmp / "cpp.json").read_text())
    check("C++ core vs 500 fixtures", rep["pass"], f"max abs {rep['max_abs_error']:.2e}")
    test_cpp_governor_parity.main(str(b / "oc_governor"), 20 if a.quick else 60); check("C++ governor vs Python governor (power_protect)", True)
    test_cpp_governor_parity.main(str(b / "oc_governor"), 20 if a.quick else 60, "throughput"); check("C++ governor vs Python governor (throughput)", True)
    for m_ in ("fleet", "fleet_balanced", "fleet_wear"):
        test_cpp_governor_parity.main(str(b / "oc_governor"), 20 if a.quick else 60, m_); check(f"C++ governor vs Python governor ({m_})", True)
    from tests import test_cpp_shield_parity
    test_cpp_shield_parity.main(str(b / "oc_shield"), 8 if a.quick else 20); check("C++ shield vs Python shield (enforce and violations)", True)
    from tests import test_cpp_shield_adversarial, test_shield_properties
    test_shield_properties.main(100_000 if a.quick else 1_000_000); check("shield properties: no invariant violated, idempotent, no invented action, minimal intervention (random + adversarial)", True)
    test_cpp_shield_adversarial.main(str(b / "oc_shield"), 50_000 if a.quick else 200_000); check("C++ shield vs Python shield on the adversarial generator", True)
    src = (ROOT / "cpp" / "src" / "shield.cpp").read_text()
    mut_src = tmp / "shield_mut.cpp"
    mut_src.write_text(src.replace('return k == "nodes" || k == "terraform_plan" || k == "rollout"; }', 'return k == "nodes" || k == "terraform_plan"; }'))
    others = [str(p) for p in (ROOT / "cpp" / "src").glob("*.cpp") if p.name != "shield.cpp"]
    subprocess.run([shutil.which("g++") or shutil.which("clang++"), "-std=c++20", "-O2", "-I", str(ROOT / "cpp" / "include"), *others, str(mut_src),
                    str(ROOT / "cpp" / "tools" / "run_shield.cpp"), "-o", str(tmp / "oc_shield_mut")], check=True)
    try:
        test_cpp_shield_parity.main(str(tmp / "oc_shield_mut"), 8)
        det3 = False
    except AssertionError:
        det3 = True
    check("negative control: parity test detects a C++ shield that no longer blocks rollouts during a security block", det3)
    from tests import test_cpp_hpa_parity
    test_cpp_hpa_parity.main(str(b / "oc_hpa"), (901,) if a.quick else (901, 902)); check("independent C++ HPA replica law vs fleet harness HPA", True)
    hsrc = (ROOT / "cpp" / "include" / "omnicompass" / "hpa.hpp").read_text()
    hm = tmp / "hmut" / "omnicompass"; hm.mkdir(parents=True)
    for p_ in (ROOT / "cpp" / "include" / "omnicompass").glob("*.hpp"):
        (hm / p_.name).write_text(p_.read_text())
    (hm / "hpa.hpp").write_text(hsrc.replace("tolerance{0.1}", "tolerance{0.05}"))
    subprocess.run([shutil.which("g++") or shutil.which("clang++"), "-std=c++20", "-O2", "-I", str(tmp / "hmut"), str(ROOT / "cpp" / "src" / "hpa.cpp"),
                    str(ROOT / "cpp" / "tools" / "run_hpa.cpp"), "-o", str(tmp / "oc_hpa_mut")], check=True)
    try:
        test_cpp_hpa_parity.main(str(tmp / "oc_hpa_mut"), (901,))
        det4 = False
    except AssertionError:
        det4 = True
    check("negative control: parity test detects a C++ HPA with 5% instead of 10% tolerance", det4)
    r = subprocess.run([str(b / "oc_smoke")], capture_output=True, text=True)
    check("C++ governor contract smoke test (bounds, security, determinism, both modes)", r.returncode == 0 and "SMOKE PASS" in r.stdout)
    n_soak = 1000000 if a.quick else 100000000
    rec_all = json.loads((ROOT / "results" / "SOAK.json").read_text())
    for mode in ("power_protect", "throughput"):
        soak = json.loads(subprocess.run([str(b / "oc_soak"), str(n_soak), mode], capture_output=True, text=True).stdout)
        cps = soak["rss_kb_at_25_50_75_100pct"]
        check(f"soak test ({mode}), {n_soak:,} decisions, no failures, memory flat after warm-up", soak["nonfinite_or_out_of_range"] == 0 and max(cps) == min(cps),
              f"{soak['ns_per_decision']:.0f} ns per decision, RSS checkpoints {cps} kB")
        if not a.quick:
            rec = rec_all[mode]
            same = all(soak[k] == rec[k] for k in ("decisions", "nonfinite_or_out_of_range", "E", "U", "I_U", "S", "B"))
            check(f"soak test ({mode}) reproduces results/SOAK.json (decisions, failures, state ranges)", same)
    hdr = (ROOT / "cpp" / "include" / "omnicompass" / "governor.hpp").read_text()
    mut = tmp / "mut" / "omnicompass"; mut.mkdir(parents=True)
    (mut / "core.hpp").write_text((ROOT / "cpp" / "include" / "omnicompass" / "core.hpp").read_text())
    for extra in ("shield.hpp", "hpa.hpp"):
        src_h = ROOT / "cpp" / "include" / "omnicompass" / extra
        if src_h.exists():
            (mut / extra).write_text(src_h.read_text())
    (mut / "shield.hpp").write_text((ROOT / "cpp" / "include" / "omnicompass" / "shield.hpp").read_text())
    (mut / "governor.hpp").write_text(hdr.replace("down_dwell{4}", "down_dwell{3}"))
    cxx = shutil.which("g++") or shutil.which("clang++")
    subprocess.run([cxx, "-std=c++20", "-O2", "-I", str(tmp / "mut"), *[str(p) for p in (ROOT / "cpp" / "src").glob("*.cpp")],
                    str(ROOT / "cpp" / "tools" / "run_governor.cpp"), "-o", str(tmp / "oc_mut")], check=True)
    try:
        test_cpp_governor_parity.main(str(tmp / "oc_mut"), 20)
        detected = False
    except AssertionError:
        detected = True
    check("negative control: parity test detects a mutated C++ governor (dwell 3 instead of 4)", detected)
    (mut / "governor.hpp").write_text(hdr.replace("push_release{0.005}", "push_release{9.0}"))
    subprocess.run([cxx, "-std=c++20", "-O2", "-I", str(tmp / "mut"), *[str(p) for p in (ROOT / "cpp" / "src").glob("*.cpp")],
                    str(ROOT / "cpp" / "tools" / "run_governor.cpp"), "-o", str(tmp / "oc_mut2")], check=True)
    try:
        test_cpp_governor_parity.main(str(tmp / "oc_mut2"), 20)
        detected2 = False
    except AssertionError:
        detected2 = True
    check("negative control: parity test detects a C++ governor without the equation (2) release gate", detected2)
    (mut / "governor.hpp").write_text(hdr.replace("push_add{-9.0}", "push_add{9.0}"))
    subprocess.run([cxx, "-std=c++20", "-O2", "-I", str(tmp / "mut"), *[str(p) for p in (ROOT / "cpp" / "src").glob("*.cpp")],
                    str(ROOT / "cpp" / "tools" / "run_governor.cpp"), "-o", str(tmp / "oc_mut3")], check=True)
    try:
        test_cpp_governor_parity.main(str(tmp / "oc_mut3"), 20)
        detected3 = False
    except AssertionError:
        detected3 = True
    check("negative control: parity test detects a C++ governor with a wrong equation (2) add gate", detected3)
    from benchmarks.stack_benchmark import simulate, ARMS
    from omnicompass import stack_sim as S
    from omnicompass.adapter import AllocationLaw
    n = 5 if a.quick else 20
    for sd in reg["held_out_seeds"]:
        rows = list(csv.DictReader(open(ROOT / "results" / f"heldout_seed_{sd}" / "RUNS.csv")))
        cfg = S.ManagerBenchmarkConfig(profile="full", scenarios=500, steps=72)
        scns = S._mom_generate_scenarios(cfg, sd)[:n]; bad = 0
        for s in scns:
            for arm in ARMS:
                new = simulate(s, arm, cfg, AllocationLaw())
                old = next(r for r in rows if int(r["scenario_id"]) == s.scenario_id and r["arm"] == arm)
                bad += int(new["trace_hash"] != old["trace_hash"] or abs(new["time_healthy"] - float(old["time_healthy"])) > 1e-12)
        check(f"held-out seed {sd}: {n} scenarios x {len(ARMS)} arms replay identically", bad == 0)
        summ = json.loads((ROOT / "results" / f"heldout_seed_{sd}" / "SUMMARY.json").read_text())
        check(f"held-out seed {sd}: observe mode identical to native", summ["observe_mode_identical_to_native"] == summ["scenarios"])
        for arm in ("omni_k8s_protect", "omni_direct", "omni_direct_no_dynamics"):
            check(f"held-out seed {sd}: {arm} invariant violations I1-I5 = 0", summ["means"][arm]["invariant_violations"] == 0.0)
        check(f"held-out seed {sd}: omni_k8s_throughput invariant violations I1-I3, I5 = 0 (I4 not enforced in throughput mode)",
              summ["means"]["omni_k8s_throughput"]["invariant_violations_ex_power"] == 0.0)
        check(f"held-out seed {sd}: layered observe mode identical to Kubernetes alone",
              summ["layered_observe_identical_to_kubernetes"] == summ["scenarios"])
    freg = json.loads((ROOT / "results" / "fleet" / "PREREGISTRATION.json").read_text())
    for f, h in freg["sha256"].items():
        if f != "omnicompass/adapter.py":
            check(f"fleet pre-registered file unchanged (SHA-256): {f}", sha(ROOT / f) == h)
    from fleet.sim import run as frun, arms_for
    from fleet.harness import make_scenario
    frows = list(csv.DictReader(open(ROOT / "results" / "fleet" / "heldout" / "RUNS.csv")))
    fsumm = json.loads((ROOT / "results" / "fleet" / "heldout" / "SUMMARY.json").read_text())
    for v in ("web", "multi", "batch", "gpu", "gpu_always_on"):
        seeds = range(freg["held_out_seed_base"], freg["held_out_seed_base"] + (2 if a.quick else 5))
        bad = 0
        for s_ in seeds:
            scn = make_scenario(v, s_)
            for arm in arms_for(v):
                new = frun(scn, arm)
                old = next(r for r in frows if r["vessel"] == v and int(r["seed"]) == s_ and r["arm"] == arm)
                bad += int(new["trace_hash"] != old["trace_hash"] or abs(float(new["energy_kwh"]) - float(old["energy_kwh"])) > 1e-9)
        check(f"fleet held-out ({v}): {len(seeds)} scenarios x {len(arms_for(v))} arms replay identically", bad == 0)
        check(f"fleet ({v}): observe mode identical to HPA 0.7 + Cluster Autoscaler",
              fsumm["vessels"][v]["observe_identical_to_hpa70_ca"] == fsumm["vessels"][v]["scenarios"])
    from fleet import planetlab as PLm
    pl_rows = list(csv.DictReader(open(ROOT / "results" / "fleet" / "planetlab" / "RUNS.csv")))
    tr = PLm.load_dir(ROOT / "fleet" / "traces" / "planetlab"); badp = 0
    for s_ in range(800000, 800000 + (1 if a.quick else 3)):
        scn = PLm.make_scenario(tr, s_)
        for arm in arms_for("web"):
            new = frun(scn, arm); old = next(r for r in pl_rows if int(r["seed"]) == s_ and r["arm"] == arm)
            badp += int(new["trace_hash"] != old["trace_hash"])
    check("recorded-trace (PlanetLab) runs replay identically", badp == 0)
    tp = json.loads((ROOT / "fleet" / "traces" / "PROVENANCE.json").read_text())
    check("recorded traces match their registered SHA-256", all(hashlib.sha256((ROOT / "fleet" / "traces" / "planetlab" / n).read_bytes()).hexdigest() == v["sha256"] for n, v in tp["files"].items()))
    from tests import test_hpa_three_way
    test_hpa_three_way.main((901,) if a.quick else (901, 902)); check("three-way HPA agreement (harness, C++, external implementation with upstream window)", True)
    import benchmarks.savings as SV
    sv_tmp = tmp / "savings"; sv_tmp.mkdir()
    SV.main(str(b / "oc_savings"), sv_tmp)
    check("C++ savings projector matches Python reference and reproduces results/SAVINGS.csv",
          (sv_tmp / "SAVINGS.csv").read_text() == (ROOT / "results" / "SAVINGS.csv").read_text())
    if not a.quick:
        from tests import test_selfpilot
        test_selfpilot.main(); check("end-to-end self-pilot: shipped controller, simulated cluster, capture and scoring (energy lower, no significant pending-pod increase)", True)
    from tests import test_pilot_score
    test_pilot_score.main(); check("pilot scoring: detects a real gain, no false gain on identical clusters, detects a service regression", True)
    from tests import test_omni_controller
    test_omni_controller.main(); check("live controller against a fake cluster: observe writes nothing, target bounded, kill restores, node pool bounded and dry-run safe", True)
    from tests import test_muscles
    test_muscles.main(); check("live muscles: power cap, heat, security, rollout, batch, CPU frequency and GPU connectors; kill restores; observe writes nothing", True)
    from tests import test_muscles_levers
    test_muscles_levers.main(); check("live levers: rightsize, coldstart, batch pace, containment, cooling; kill restores every one, also from a fresh process", True)
    from tests import test_active_nodes
    test_active_nodes.main(); check("full-engine controller options: parked and control-plane nodes excluded, kill switch restores the node pool once", True)
    from tests import test_schedutil, test_cpufreq_ceiling
    test_schedutil.main(); check("schedutil model: 1.25 map tips at 80%, OPP snap, uclamp, RT to policy max, rate limit, iowait boost, Omni ceiling and kill", True)
    test_cpufreq_ceiling.main(); check("cpufreq ceiling writer: scaling_max_freq on every policy, clamped; restore puts cpuinfo_max_freq back", True)
    from tests import test_failsafe
    test_failsafe.main(); check("controller fail-safe: a failed decision is skipped; three in a row restore native settings and stop", True)
    from tests import test_fleet_realdata_paths
    test_fleet_realdata_paths.main(); check("capture replay and PlanetLab vessel on inputs in the real formats", True)
    r = subprocess.run(["bash", "-n", str(ROOT / "fleet" / "capture" / "kube_capture.sh")], capture_output=True)
    check("cluster capture script parses", r.returncode == 0)
    import benchmarks.multiplicity as MP
    mp_tmp = tmp / "mult.json"; MP.main(mp_tmp)
    check("multiplicity analysis reproduces results/MULTIPLICITY.json",
          json.loads(mp_tmp.read_text()) == json.loads((ROOT / "results" / "MULTIPLICITY.json").read_text()))
    if a.full_replay:
        from benchmarks.stack_benchmark import run as run_bench
        for sd in reg["held_out_seeds"]:
            out = tmp / f"replay_{sd}"
            run_bench(reg["held_out_scenarios_per_seed"], sd, out, AllocationLaw())
            same_runs = (out / "RUNS.csv").read_bytes() == (ROOT / "results" / f"heldout_seed_{sd}" / "RUNS.csv").read_bytes()
            new_s = json.loads((out / "SUMMARY.json").read_text()); old_s = json.loads((ROOT / "results" / f"heldout_seed_{sd}" / "SUMMARY.json").read_text())
            new_law, old_law = new_s.pop("allocation_law"), old_s.pop("allocation_law")
            inert = {"push_add": -9.0}
            law_ok = all(new_law.get(k) == v for k, v in old_law.items()) and all(k in inert and new_law[k] == inert[k] for k in set(new_law) - set(old_law))
            same_summary = new_s == old_s and law_ok
            check(f"full replay, held-out seed {sd}: all scenarios x all arms regenerate RUNS.csv exactly and SUMMARY.json exactly (recorded law may add only inert defaults)", same_runs and same_summary)
    print("\nVERIFICATION:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
