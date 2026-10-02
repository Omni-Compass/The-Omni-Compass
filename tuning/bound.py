# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Physical bound: what a controller with perfect knowledge of the future could achieve on node-hours and machine churn.

For each scenario the pods (and their CPU requests) are those produced by HPA 70% (the platforms' setting). A node count
n(t) is feasible when it holds every pod: n(t) >= ceil(requests(t) / (cores x ALLOC)), within [min, max] nodes. Dynamic
programming finds, for a price lambda on node-hours, the trajectory minimising starts+stops + lambda x node-ticks; sweeping
lambda traces the frontier: the fewest starts+stops possible for each node-hour budget. (Boot delay is ignored, which
only favours the bound.) If a competitor's node-hours and another competitor's starts+stops lie below this frontier, no
controller whatsoever can match both, Omni-Compass included.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario, TICK
from fleet.sim import ALLOC
from tuning.league import COMPETITORS, SEEDS
from tuning.speed_search import gauges


def frontier(req, cores, lo, hi, n0):
    need = np.clip(np.ceil(np.asarray(req) / (cores * ALLOC) - 1e-9), lo, hi).astype(int)
    N = np.arange(hi + 1)
    pts = []
    for lam in [0.0, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 1e9]:
        cost = np.where(N == n0, 0.0, np.inf); cnt = np.zeros(hi + 1); nh = np.zeros(hi + 1)
        # track churn and node-ticks along the argmin path
        for t in range(len(need)):
            trans = cost[None, :] + np.abs(N[:, None] - N[None, :])          # to i from j
            j = np.argmin(trans, axis=1)
            c_new = trans[N, j] + lam * N
            c_new[N < need[t]] = np.inf
            cnt = cnt[j] + np.abs(N - j); nh = nh[j] + N
            cost = c_new
        k = int(np.argmin(cost))
        pts.append((float(nh[k] * TICK / 3600.0), float(cnt[k])))
    return pts


if __name__ == "__main__":
    out = {}
    for v in ("web", "batch", "gpu", "multi"):
        rows = []
        for s in SEEDS["dev"][:4]:
            sc = make_scenario(v, s)
            sim_slo.REC = []
            comp = {c: gauges(sim_slo.run(sc, c)) for c in COMPETITORS}
            rec = sim_slo.REC[:len(sim_slo.REC) // len(COMPETITORS)]
            sim_slo.REC = None
            # requests trace of the first competitor run (HPA 70 pods); multi: sum the per-cluster frontiers
            fr = None
            for ci, cl in enumerate(sc.clusters):
                p = cl.pool
                f = frontier([r[ci] for r in rec], p.cores, p.min_nodes, p.max_nodes, p.nodes)
                fr = f if fr is None else [(a[0] + b[0], a[1] + b[1]) for a, b in zip(fr, f)]
            min_nh = min(comp[c]["node_hours"] for c in COMPETITORS)
            min_ss = min(comp[c]["start_stop"] for c in COMPETITORS)
            best_ss_at_nh = min((ss for nh, ss in fr if nh <= min_nh + 1e-6), default=None)
            rows.append({"seed": s, "min_competitor_node_hours": min_nh, "min_competitor_start_stop": min_ss,
                         "fewest_start_stop_possible_at_that_node_hours": best_ss_at_nh, "frontier": fr})
            print(v, s, f"best packer node-hours {min_nh:.1f}; fewest starts+stops of any platform {min_ss}; "
                  f"a perfect controller needs at least {best_ss_at_nh} starts+stops to reach {min_nh:.1f} node-hours", flush=True)
        out[v] = rows
    (ROOT / "tuning/BOUND_DEV.json").write_text(json.dumps(out, indent=1))
