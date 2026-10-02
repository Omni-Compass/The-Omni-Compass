#!/usr/bin/env python3
"""Pool the shards of a six-organism run (tools/run_scale.py, one SCALE.json per shard) into one receipt.

  python3 tools/pool_scale.py OUT.md parts/*/SCALE.json
"""
import glob, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from realms.harness import summarize, label  # noqa: E402
from tools.run_scale import ORGS, rows_for  # noqa: E402


def main(out, *paths):
    files = [p for g in paths for p in glob.glob(g)]
    per, scale, commits = {}, None, set()
    for f in files:
        d = json.loads(Path(f).read_text())
        scale = d["scale"]; commits.add(d["commit"][:12])
        for k, runs in d["per_run"].items():
            per.setdefault(k, {}).update(runs)
    L = [f"# Six organisms, {max(len(v) for v in per.values())} runs, {scale}x size (pooled from {len(files)} shards)", "",
         f"Evidence class **S** (models). Commit(s) {', '.join(sorted(commits))}. Native: each organism's own controllers. "
         "Omni: the bowl law on every muscle. Band first: no win unless the time over the service line is no higher than "
         "native's (violations at or under 0 pp).", "",
         "| # | Organism | Muscles | Runs | Label | Band first | Work per energy | Work | Energy | Violations (pp) | Knobs handed back |",
         "|---|---|---:|---:|---|---|---:|---:|---:|---:|---|"]
    summ = {}
    for num, (k, nm) in ORGS.items():
        if k not in per:
            continue
        xs = [per[k][s] for s in sorted(per[k], key=int)]
        sm = summarize(xs); ok = all(c["restore_ok"] for c in xs)
        lab = label(xs, valid=ok); band = "held" if sm["viol_pp"][0] <= 0 else "NOT held"
        summ[k] = {"runs": len(xs), "label": lab, "band_first": band, **{q: list(v) for q, v in sm.items()}}
        f = lambda q, s=100.0, u="%": f"{s * sm[q][0]:+.3f}{u} ({s * sm[q][1]:+.3f} to {s * sm[q][2]:+.3f})"
        L.append(f"| {num} | {nm} | {len(rows_for(k, scale))} | {len(xs)} | **{lab}** | {band} | {f('primary')} | {f('work')} | "
                 f"{f('energy')} | {f('viol_pp', 1.0, '')} | {ok} |")
    Path(out).write_text("\n".join(L) + "\n")
    Path(out).with_suffix(".json").write_text(json.dumps({"scale": scale, "summary": summ}, indent=1) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:])
