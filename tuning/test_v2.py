# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import benchmarks.stack_benchmark as sb
from tuning.tune_stack import scenarios, run_arm, compare, DEV_SEEDS, AllocationLaw
from tuning import law_v2
n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
sets = [scenarios(n, s) for s in DEV_SEEDS]
k8s = [sb.simulate(s, "k8s_ref_70", cfg, AllocationLaw()) for cfg, scns in sets for s in scns]
cands = {"B_frozen": ("omni_k8s_throughput", {}), "B_tuned": ("omni_k8s_throughput", {'down_dwell': 20, 'down_after_add': 3}),
         "C_thr_tuned": ("omni_direct_throughput", {'down_band': 8, 'down_dwell': 10, 'down_after_add': 3, 'U_gate': 0.9, 'cap_min': 0.65, 'rho0': 0.85})}
res = {}
for v2 in (False, True):
    un = law_v2.install(sb) if v2 else (lambda: None)
    try:
        for name, (arm, over) in cands.items():
            rows = [r for cfg, scns in sets for r in run_arm(arm, over, cfg, scns)]
            res[name + ("_v2" if v2 else "")] = compare(k8s, rows)
    finally:
        un()
keys = list(next(iter(res.values())).keys())
print(f"{'gauge':22}" + "".join(f"{k:>16}" for k in res))
for m in keys:
    print(f"{m:22}" + "".join(f"{100*res[k][m]['rel']:+14.1f}%{'!' if res[k][m]['worse'] else ' '}" for k in res))
print("worse count:", {k: sum(v['worse'] for v in r.values()) for k, r in res.items()})
json.dump(res, open(ROOT / "tuning/V2_DEV.json", "w"), indent=1)
