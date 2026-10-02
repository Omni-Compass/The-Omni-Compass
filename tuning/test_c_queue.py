# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
import sys, itertools
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import benchmarks.stack_benchmark as sb
from tuning.tune_stack import scenarios, run_arm, compare, DEV_SEEDS, AllocationLaw
sets = [scenarios(40, s) for s in DEV_SEEDS]
k8s = [sb.simulate(s, "k8s_ref_70", cfg, AllocationLaw()) for cfg, scns in sets for s in scns]
base = {'down_band': 8, 'down_dwell': 10, 'down_after_add': 3, 'U_gate': 0.9, 'cap_min': 0.65}
rows_out = []
for sfc, rho0, kq, up in itertools.product([True, False], [0.85, 0.75, 0.65], [0.3, 0.795, 1.5], [2, 8]):
    over = dict(base, size_at_full_cap=sfc, rho0=rho0, rho_min=min(0.627, rho0), kq=kq, up_max=up)
    c = compare(k8s, [r for cfg, scns in sets for r in run_arm("omni_direct_throughput", over, cfg, scns)])
    rows_out.append((sum(v["worse"] for v in c.values()), c["mean_queue"]["rel"], c["energy_kwh"]["rel"], over, c))
rows_out.sort(key=lambda r: (r[0], r[1]))
for w, q, e, over, c in rows_out[:6]:
    print(f"worse {w}  queue {100*q:+.0f}%  energy {100*e:+.1f}%  node_hours {100*c['node_hours']['rel']:+.1f}%  wear {100*c['node_start_stop']['rel']:+.0f}%  healthy {100*c['time_healthy']['rel']:+.1f}%  avail {100*c['availability']['rel']:+.2f}%  {over}")
best = min(rows_out, key=lambda r: r[1]); print("lowest queue:", f"{100*best[1]:+.0f}%", "energy", f"{100*best[2]:+.1f}%", best[3])
