# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Run the pre-registered amendment (tuning/PREREGISTRATION_AMENDMENT_2026-09-26.json) once on the new held-out seeds."""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import benchmarks.stack_benchmark as sb
from tuning.tune_stack import scenarios, run_arm, LOWER, HIGHER, AllocationLaw
P = json.loads((ROOT / "tuning/PREREGISTRATION_AMENDMENT_2026-09-26.json").read_text())
V = P["variants"]
arms = {"A_k8s": ("k8s", {}), "B_frozen": ("omni_k8s_throughput", {}), "C_frozen": ("omni_direct", {}),
        "B_wear": ("omni_k8s_throughput", V["B_wear"]["overrides_after_throughput_mode"]),
        "C_throughput": ("omni_direct_throughput", V["C_throughput"]["overrides"])}
out = {"seeds": P["new_held_out_seeds"], "scenarios_per_seed": P["scenarios_per_seed"], "means": {}, "paired": {}}
per = {}
for seed in P["new_held_out_seeds"]:
    cfg, scns = scenarios(P["scenarios_per_seed"], seed)
    for name, (arm, over) in arms.items():
        rows = [sb.simulate(s, "k8s_ref_70", cfg, AllocationLaw()) for s in scns] if arm == "k8s" else run_arm(arm, over, cfg, scns)
        per.setdefault(name, {})[seed] = rows
rng = np.random.default_rng(12345)
for name in arms:
    out["means"][name] = {m: float(np.mean([r[m] for s in P["new_held_out_seeds"] for r in per[name][s]])) for m in LOWER + HIGHER}
for name in [n for n in arms if n != "A_k8s"]:
    out["paired"][name] = {}
    for m in LOWER + HIGHER:
        cis = []
        for s in P["new_held_out_seeds"]:
            d = np.array([c[m] - a[m] for a, c in zip(per["A_k8s"][s], per[name][s])])
            bs = d[rng.integers(0, len(d), (3000, len(d)))].mean(1); cis.append([float(x) for x in np.percentile(bs, [2.5, 97.5])])
        up = all(lo > 0 for lo, hi in cis); down = all(hi < 0 for lo, hi in cis)
        better = (down if m in LOWER else up); worse = (up if m in LOWER else down)
        out["paired"][name][m] = {"ci95_per_seed": cis, "verdict": "better" if better else "worse" if worse else "not significant"}
(ROOT / "tuning/HELDOUT_AMENDMENT.json").write_text(json.dumps(out, indent=1))
A = out["means"]["A_k8s"]
print(f"{'gauge':22}{'A k8s':>12}" + "".join(f"{n:>24}" for n in arms if n != "A_k8s"))
for m in LOWER + HIGHER:
    line = f"{m:22}{A[m]:12.3f}"
    for n in [n for n in arms if n != "A_k8s"]:
        v = out["means"][n][m]; rel = (v - A[m]) / abs(A[m]) * 100 if A[m] else 0.0
        tag = {"better": "+", "worse": "!", "not significant": " "}[out["paired"][n][m]["verdict"]]
        line += f"{v:12.3f} {rel:+7.1f}% {tag}  "
    print(line)
print("worse:", {n: sum(v["verdict"] == "worse" for v in out["paired"][n].values()) for n in out["paired"]})
