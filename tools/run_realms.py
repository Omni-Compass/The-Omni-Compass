"""Run the realm harness and write its tables (docs/REALMS.md, preregistered in docs/REALMS_PREREGISTRATION.md).

  python3 tools/run_realms.py                       # the preregistered run: seeds 1000-1009, results/realms/
  python3 tools/run_realms.py --seeds 0 1 --out /tmp/realms-dev   # a look on development seeds (never reported)

Every muscle alone (native, watch, omni; plus the fixed calm setpoint for setpoint muscles), then five organisms: each
realm, and all 656 muscles together. Writes MUSCLES.csv (one row per muscle), REALMS.json (everything), REALMS.md (the
tables), RUN.json (commit, seeds, fingerprints) and SHA256SUMS.txt. The preregistered seeds run only on committed code.
"""
import argparse, csv, hashlib, json, math, os, subprocess, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from realms.harness import (catalog, run_muscle, run_organism, paired, paired_organism, label, summarize,  # noqa
                            FIXED)

PREREG_SEEDS = list(range(1000, 1010))
REALMS = ["compute_ai_cloud", "physics_robotics_autonomous", "energy_facility_industrial", "distribution_specialized"]
NAMES = {"compute_ai_cloud": "Compute / AI / Cloud", "physics_robotics_autonomous": "Physics / Robotics / Autonomous",
         "energy_facility_industrial": "Energy / Facility / Industrial",
         "distribution_specialized": "Distribution / Specialized", "organism_656": "The whole tower (656 muscles)"}
LABELS = ["SUPERIOR WITHIN GUARDRAILS", "ENERGY IMPROVEMENT WITH SERVICE TRADEOFF", "NONINFERIOR / INCONCLUSIVE",
          "NOT ESTABLISHED", "WORSE", "INVALID"]
FROZEN = ["realms", "omnicompass", "tools/run_realms.py", "docs/REALMS_PREREGISTRATION.md"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tree_sha(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode()); h.update(sha(ROOT / p).encode())
    return h.hexdigest()


def muscle_job(args):
    row, seeds = args
    runs = [run_muscle(row, s) for s in seeds]
    valid = all(r["watch_equal"] and r["omni"]["restore_ok"] for r in runs)
    per = [paired(r["omni"], r["native"]) for r in runs]
    out = {"row": row, "valid": valid, "label": label(per, valid), "summary": summarize(per), "per_seed": per,
           "writes": sum(r["omni"]["writes"] for r in runs) / len(runs),
           "native_viol_share": sum(r["native"]["viol"] / r["native"]["steps"] for r in runs) / len(runs)}
    if row["knob"] == "setpoint":
        fx = [paired(r[FIXED], r["native"]) for r in runs]
        out["fixed_calm"] = {"label": label(fx), "summary": summarize(fx)}
    return out


def organism_job(args):
    name, rows, seed = args
    return name, seed, run_organism(rows, seed)


def fmt(m, scale=100.0, unit="%"):
    return f"{m[0] * scale:+.1f}{unit} ({m[1] * scale:+.1f} to {m[2] * scale:+.1f})"


def write_md(out, res, orgs, run):
    L = []
    w = L.append
    w("# The realms: 656 muscles on modelled plants, native against Omni on top")
    w("")
    w(f"Evidence class **S** (simulation). Run {run['started']}, commit `{run['commit'][:12]}`, seeds "
      f"{run['seeds'][0]}-{run['seeds'][-1]} ({len(run['seeds'])} paired seeds per muscle and per organism). "
      "Preregistered in `docs/REALMS_PREREGISTRATION.md`; harness `realms/`; every plant and its native controller in "
      "`realms/plants.py`, every number in `realms/presets.py`. The governor is the frozen "
      "`omnicompass.adapter.Governor`, unchanged.")
    w("")
    w("Primary outcome: work per energy, Omni against native, with its 95% interval over seeds. Guardrails: work not "
      "lower by more than 1%, share of periods in violation not higher by more than 1 percentage point. Labels by rule.")
    w("")
    w("These are models. A model's energy is not a meter's, and a plant written by the same people who wrote the "
      "governor is not an independent test. What a row here can show is whether the governor's law, applied to that "
      "knob, helps or hurts the model, and where it breaks.")
    w("")
    w("## The five organisms")
    w("")
    w("| Organism | Muscles | Label | Work per energy | Work | Energy | Violations (pp) | Valid |")
    w("|---|---:|---|---:|---:|---:|---:|---|")
    for name in [n for n in REALMS + ["organism_656"] if n in orgs]:
        o = orgs[name]
        s = o["summary"]
        w(f"| {NAMES[name]} | {o['n']} | **{o['label']}** | {fmt(s['primary'])} | {fmt(s['work'])} | "
          f"{fmt(s['energy'])} | {fmt(s['viol_pp'], 1.0, '')} | {'yes' if o['valid'] else 'NO'} |")
    w("")
    w("## Every muscle alone, by realm")
    w("")
    w("| Realm | Muscles | " + " | ".join(LABELS) + " |")
    w("|---|---:|" + "---:|" * len(LABELS))
    for realm in REALMS:
        rs = [r for r in res if r["row"]["realm"] == realm]
        c = Counter(r["label"] for r in rs)
        w(f"| {NAMES[realm]} | {len(rs)} | " + " | ".join(str(c.get(l, 0)) for l in LABELS) + " |")
    c = Counter(r["label"] for r in res)
    w(f"| **All** | {len(res)} | " + " | ".join(f"**{c.get(l, 0)}**" for l in LABELS) + " |")
    w("")
    w("## By knob: what kind of authority Omni held")
    w("")
    w("| Knob | Muscles | " + " | ".join(LABELS) + " | Median work per energy |")
    w("|---|---:|" + "---:|" * len(LABELS) + "---:|")
    for knob in ("capacity", "setpoint", "power", "admission"):
        rs = [r for r in res if r["row"]["knob"] == knob]
        if not rs:
            continue
        c = Counter(r["label"] for r in rs)
        med = sorted(r["summary"]["primary"][0] for r in rs)[len(rs) // 2]
        w(f"| {knob} | {len(rs)} | " + " | ".join(str(c.get(l, 0)) for l in LABELS) + f" | {med * 100:+.1f}% |")
    w("")
    sp = [r for r in res if "fixed_calm" in r]
    if sp:
        better = sum(1 for r in sp if r["fixed_calm"]["summary"]["primary"][0] > r["summary"]["primary"][0])
        w("## Setpoint muscles: Omni against simply fixing the setpoint at the band's calm end")
        w("")
        w(f"For {better} of {len(sp)} setpoint muscles, a fixed setpoint at the calm end of the declared band gave more "
          "work per energy than Omni moving it. On those muscles the gain is the band, not the governor. The fixed "
          "setpoint's own label (with its service guardrails) is in `MUSCLES.csv`.")
        w("")
    w("## By family")
    w("")
    w("| Realm | Family | Plant | Muscles | Superior | Tradeoff | Inconclusive | Not established | Worse | Invalid | "
      "Median work per energy |")
    w("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    fam = defaultdict(list)
    for r in res:
        fam[(r["row"]["realm"], r["row"]["family"])].append(r)
    for (realm, f), rs in sorted(fam.items()):
        c = Counter(r["label"] for r in rs)
        med = sorted(r["summary"]["primary"][0] for r in rs)[len(rs) // 2]
        w(f"| {NAMES[realm]} | {f} | {rs[0]['row']['template']} ({rs[0]['row']['preset']}) | {len(rs)} | "
          + " | ".join(str(c.get(l, 0)) for l in LABELS) + f" | {med * 100:+.1f}% |")
    w("")
    w("## Largest gains and largest losses (single muscles, by mean work per energy)")
    w("")
    srt = sorted(res, key=lambda r: r["summary"]["primary"][0])
    w("| Muscle | Family | Knob | Label | Work per energy | Work | Violations (pp) |")
    w("|---|---|---|---|---:|---:|---:|")
    for r in srt[-10:][::-1] + srt[:10]:
        s = r["summary"]
        w(f"| {r['row']['muscle']} | {r['row']['family']} | {r['row']['knob']} | {r['label']} | {fmt(s['primary'])} | "
          f"{fmt(s['work'])} | {fmt(s['viol_pp'], 1.0, '')} |")
    w("")
    w("## Validity")
    w("")
    inv = [r for r in res if not r["valid"]]
    w(f"- Watch equal to native and the kill switch handing back the knob: {len(res) - len(inv)} of {len(res)} muscles; "
      f"{sum(1 for o in orgs.values() if o['valid'])} of {len(orgs)} organisms.")
    w("- Raw per-seed contrasts: `REALMS.json`. One row per muscle: `MUSCLES.csv`. Fingerprints: `RUN.json`, "
      "`SHA256SUMS.txt`.")
    (out / "REALMS.md").write_text("\n".join(L) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=PREREG_SEEDS)
    ap.add_argument("--out", default=str(ROOT / "results" / "realms"))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--limit", type=int, default=0, help="first N muscles only (a look; never reported)")
    a = ap.parse_args(argv)
    prereg = a.seeds == PREREG_SEEDS and not a.limit
    dirty = subprocess.run(["git", "status", "--porcelain", "--"] + FROZEN, cwd=ROOT, capture_output=True,
                           text=True).stdout.strip()
    if prereg and dirty:
        print("the preregistered seeds run only on committed code; uncommitted changes in:\n" + dirty)
        return 1
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows = catalog()
    if a.limit:
        rows = rows[:a.limit]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    frozen_files = [str(p.relative_to(ROOT)) for d in ("realms", "omnicompass") for p in sorted((ROOT / d).rglob("*"))
                    if p.is_file() and p.suffix in (".py", ".csv", ".json")]
    run = {"started": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "commit": commit, "seeds": a.seeds,
           "preregistered": prereg, "dirty": bool(dirty), "muscles": len(rows),
           "frozen_tree_sha256": tree_sha(frozen_files + ["tools/run_realms.py"]),
           "catalog_sha256": sha(ROOT / "realms" / "catalog.csv"), "engine_sha256": sha(ROOT / "omnicompass" / "core.py"),
           "governor_sha256": sha(ROOT / "omnicompass" / "adapter.py")}
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        res = list(ex.map(muscle_job, [(r, a.seeds) for r in rows], chunksize=4))
        print(f"muscles: {len(res)} in {time.time() - t0:.0f} s", flush=True)
        groups = {realm: [r for r in rows if r["realm"] == realm] for realm in REALMS}
        groups["organism_656"] = rows
        jobs = [(name, rs, s) for name, rs in groups.items() if rs for s in a.seeds]
        raw = defaultdict(dict)
        for name, seed, o in ex.map(organism_job, jobs):
            raw[name][seed] = o
    print(f"organisms done in {time.time() - t0:.0f} s", flush=True)
    orgs = {}
    for name, by_seed in raw.items():
        runs = [by_seed[s] for s in a.seeds]
        valid = all(o["watch_equal"] and o["omni"]["restore_ok"] for o in runs)
        per = [paired_organism(o["omni"], o["native"]) for o in runs]
        orgs[name] = {"n": len(groups[name]), "valid": valid, "label": label(per, valid), "summary": summarize(per),
                      "per_seed": per, "writes": sum(o["omni"]["writes"] for o in runs) / len(runs)}
    run["elapsed_s"] = round(time.time() - t0)
    with (out / "MUSCLES.csv").open("w", newline="") as f:
        cols = ["muscle_id", "family", "muscle", "realm", "template", "preset", "knob", "label", "primary", "primary_lo",
                "primary_hi", "work", "work_lo", "energy", "viol_pp", "viol_pp_hi", "writes_per_run",
                "native_viol_share", "valid", "fixed_calm_label", "fixed_calm_primary"]
        wr = csv.writer(f); wr.writerow(cols)
        for r in res:
            s, row = r["summary"], r["row"]
            fx = r.get("fixed_calm")
            wr.writerow([row["muscle_id"], row["family"], row["muscle"], row["realm"], row["template"], row["preset"],
                         row["knob"], r["label"], *(f"{x:.5f}" for x in s["primary"]), f"{s['work'][0]:.5f}",
                         f"{s['work'][1]:.5f}", f"{s['energy'][0]:.5f}", f"{s['viol_pp'][0]:.3f}",
                         f"{s['viol_pp'][2]:.3f}", f"{r['writes']:.1f}", f"{r['native_viol_share']:.4f}", r["valid"],
                         fx["label"] if fx else "", f"{fx['summary']['primary'][0]:.5f}" if fx else ""])
    (out / "REALMS.json").write_text(json.dumps({"run": run, "organisms": orgs, "muscles": res}, indent=1) + "\n")
    (out / "RUN.json").write_text(json.dumps(run, indent=1) + "\n")
    write_md(out, res, orgs, run)
    files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (out / "SHA256SUMS.txt").write_text("".join(f"{sha(p)}  {p.name}\n" for p in files))
    print((out / "REALMS.md").read_text().split("## Every muscle")[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
