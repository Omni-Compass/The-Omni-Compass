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
    total = max(len(v) for v in per.values())
    L = [f"# Six organisms at {scale}x size, up to {total} runs (pooled from {len(files)} shards)", "",
         f"Evidence class **S** (models). Commit(s) {', '.join(sorted(commits))}. Native: each organism's own controllers. "
         "Omni: the bowl law on every muscle. Each block is the first N runs (seeds 7000 on), so 1, 10, 100 and 1,000 "
         "are nested. Band first: no win unless the time over the service line is no higher than native's.", ""]
    summ = {}
    for n in [x for x in (1, 10, 100, 1000) if x <= total]:
        L += [f"## {n} run{'s' if n > 1 else ''}", "",
              "| # | Organism | Muscles | Runs | Label | Band first | Work per energy | Work | Energy | Violations (pp) | Knobs handed back |",
              "|---|---|---:|---:|---|---|---:|---:|---:|---:|---|"]
        for num, (k, nm) in ORGS.items():
            if k not in per:
                continue
            xs = [per[k][s] for s in sorted(per[k], key=int)][:n]
            ok = all(c["restore_ok"] for c in xs)
            if len(xs) >= 2:
                sm = summarize(xs); lab = label(xs, valid=ok)
            else:
                sm = {q: (xs[0][q], xs[0][q], xs[0][q]) for q in ("primary", "work", "energy", "viol_pp")}; lab = "ONE RUN (no label)"
            band = "held" if sm["viol_pp"][0] <= 0 else "NOT held"
            summ.setdefault(str(n), {})[k] = {"runs": len(xs), "label": lab, "band_first": band, **{q: list(v) for q, v in sm.items()}}
            f = lambda q, s=100.0, u="%": f"{s * sm[q][0]:+.3f}{u}" + (f" ({s * sm[q][1]:+.3f} to {s * sm[q][2]:+.3f})" if len(xs) > 1 else "")
            L.append(f"| {num} | {nm} | {len(rows_for(k, scale))} | {len(xs)} | **{lab}** | {band} | {f('primary')} | {f('work')} | "
                     f"{f('energy')} | {f('viol_pp', 1.0, '')} | {ok} |")
        L.append("")
    Path(out).write_text("\n".join(L) + "\n")
    Path(out).with_suffix(".json").write_text(json.dumps({"scale": scale, "summary": summ}, indent=1) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(*sys.argv[1:])
