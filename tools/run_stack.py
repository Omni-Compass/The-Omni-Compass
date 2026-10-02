"""The stacked organism: the four realm organisms on one clock, every muscle as often as it appears (1,226 with the
duplicates), native against Omni (docs/REALMS_PREREGISTRATION.md, round 4).

  python3 tools/run_stack.py                         # preregistered seeds 4000-4009, results/realms/stack/

Three arms per seed: native (no governor), separate (one governor per realm), one (one governor over the whole stack).
Checks that the stacked native run equals each realm's own native run, plant by plant. Writes STACK.md, STACK.json,
RUN.json and SHA256SUMS.txt.
"""
import hashlib, json, os, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realms.harness import catalog, run_stack, paired_organism, label, summarize  # noqa: E402

SEEDS = list(range(4000, 4010))
REALMS = ["compute_ai_cloud", "physics_robotics_autonomous", "energy_facility_industrial", "distribution_specialized"]
FROZEN = ["realms", "omnicompass", "tools/run_stack.py", "docs/REALMS_PREREGISTRATION.md"]


def job(seed):
    rows = catalog()
    rr = [[r for r in rows if realm in r["realms"].split(";")] for realm in REALMS]
    return seed, run_stack(rr, seed)


def fmt(m, scale=100.0, unit="%"):
    return f"{m[0] * scale:+.2f}{unit} ({m[1] * scale:+.2f} to {m[2] * scale:+.2f})"


def main(argv=None):
    seeds = [int(x) for x in (argv or sys.argv[1:])] or SEEDS
    prereg = seeds == SEEDS
    dirty = subprocess.run(["git", "status", "--porcelain", "--"] + FROZEN, cwd=ROOT, capture_output=True,
                           text=True).stdout.strip()
    if prereg and dirty:
        print("the preregistered seeds run only on committed code; uncommitted changes in:\n" + dirty)
        return 1
    out = ROOT / "results" / "realms" / "stack"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with ProcessPoolExecutor(os.cpu_count() or 2) as ex:
        runs = dict(ex.map(job, seeds))
    res = {}
    valid = all(runs[s]["native_equal"] and runs[s]["separate"]["restore_ok"] and runs[s]["one"]["restore_ok"]
                for s in seeds)
    for name, a, b in (("one governor vs native", "one", "native"), ("separate governors vs native", "separate", "native"),
                       ("one governor vs separate governors", "one", "separate")):
        per = [paired_organism(runs[s][a], runs[s][b]) for s in seeds]
        res[name] = {"label": label(per, valid), "summary": summarize(per), "per_seed": per}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    run = {"started": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "commit": commit, "seeds": seeds,
           "preregistered": prereg, "dirty": bool(dirty), "elapsed_s": round(time.time() - t0),
           "muscles_stacked": len(runs[seeds[0]]["native"]["plants"]),
           "native_equal_every_seed": all(runs[s]["native_equal"] for s in seeds)}
    L = ["# The stacked organism: all four realms on one clock, native against Omni", "",
         f"Evidence class **S** (simulation). Commit `{commit[:12]}`, seeds {seeds[0]}-{seeds[-1]}, "
         f"{run['muscles_stacked']} muscles stacked: the four realm organisms (345 + 262 + 282 + 337), every muscle as "
         "often as it appears in them, duplicates included. A duplicate is still a muscle that has to converge. Each "
         "realm keeps its own internal coupling (heat into its cooling, load onto its batteries). Preregistered: "
         "`docs/REALMS_PREREGISTRATION.md`, round 4.", "",
         f"- **Stacking changes nothing natively:** the stacked native run equals each realm's own native run, plant by "
         f"plant, on {'every seed' if run['native_equal_every_seed'] else 'NOT every seed'}.",
         "- **Kill switch:** every knob handed back under both governor arms on every seed: "
         f"{'yes' if valid else 'NO'}.", "",
         "| Comparison | Label | Work per energy | Work | Energy | Violations (pp) |", "|---|---|---:|---:|---:|---:|"]
    for name, r in res.items():
        s = r["summary"]
        L.append(f"| {name} | **{r['label']}** | {fmt(s['primary'])} | {fmt(s['work'])} | {fmt(s['energy'])} | "
                 f"{fmt(s['viol_pp'], 1.0, '')} |")
    L += ["", "Work is the mean over the stacked muscles of work with Omni over work native; energy is total joules; "
          "violations are the change in the share of periods any muscle was out of its service target. Labels by the "
          "preregistered rule. These are models, not meters."]
    (out / "STACK.md").write_text("\n".join(L) + "\n")
    (out / "STACK.json").write_text(json.dumps({"run": run, "results": res}, indent=1) + "\n")
    (out / "RUN.json").write_text(json.dumps(run, indent=1) + "\n")
    files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (out / "SHA256SUMS.txt").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
