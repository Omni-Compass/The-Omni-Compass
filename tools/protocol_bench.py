"""OmniCompass Runtime Benchmark Protocol (benchmark_protocol.docx), stage 1, on the fleet plant (fleet/sim_slo.py).

Same scenarios, same faults, every architecture:
  A  each platform alone        k8s_hpa70_ca, openshift, gke_optimize, aks_nap, turbonomic, cast_ai, spot_ocean
  B  Omni-Compass on top of it  omniB:<platform> with the frozen per-platform settings (tuning/B_SETTINGS_PER_PLATFORM.json)
  C  Omni-Compass alone         C-hpa: the held-out C league pick (HPA kept);  C-strict: the closure law, HPA replaced
                                (settings: tuning/CLOSURE_SEARCH2_DEV.json, else CLOSURE_SEARCH_DEV.json, else defaults)

Stress levels 1-5 (protocol section 6). Level L injects L fault events, times drawn uniformly in [120, 1200) ticks, each
one of (drawn with the seed, identical for every arm):
  node_crash      L x 10% of the cluster's running machines die at once (at least one)
  load_spike      every workload in the cluster: demand x (1 + 0.5 L) for 20-80 ticks        (queue overload, scaling)
  service_crash   L x 20% of the cluster's services lose half their pods (crash loop, restart churn) and queue
                  two ticks of demand as backlog
  cpu_pressure    a noisy neighbour: extra demand of L x 8% of the cluster's allocatable cores for 40-160 ticks,
                  spread over the workloads
Admissible basin, per tick (declared before any run): worst response time <= 1000 ms (10 x service time),
queue ratio < 0.28, pending pods <= 5% of requested, site power <= 1.02 x limit, thermal < 0.96.
Gauges (protocol section 7):
  conveyed          every fault recovered within 20 min (80 ticks) AND all clusters in the basin for the last 10 min
  recovery time     from a fault to the first tick that starts 2 min (8 ticks) in the basin; unrecovered = to the end
  failure persist.  minutes outside the basin
  pages             out-of-basin episodes lasting 5 min or longer (the Prometheus `for: 5m` rule): each one calls a
                    human (the protocol's human intervention count; nobody intervenes in the simulation)
  max error / CPU / queue / latency, timeouts (demand share with response > 2 s), work completed, energy
Usage: python tools/protocol_bench.py [runs_per_level=100]   ->  results/protocol/{raw_results.csv, summary_results.csv,
PROTOCOL_SUMMARY.json}
"""
import csv, json, math, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from fleet import sim_slo
from fleet.harness import make_scenario, STEPS, TICK
from fleet.sim_slo import BLaw, DirectLaw
from omnicompass.speed import SpeedLaw
from omnicompass.closure import ClosureLaw
from tuning.league import candidates

PLATFORMS = ["k8s_hpa70_ca", "openshift", "gke_optimize", "aks_nap", "turbonomic", "cast_ai", "spot_ocean"]
VESSELS = ["web", "multi", "batch", "gpu"]
LEVELS = [1, 2, 3, 4, 5]
SEED0 = 900001
R_LIM, Q_LIM, PEND_LIM, P_LIM, TH_LIM = 1000.0, 0.28, 0.05, 1.02, 0.96
REC_OK, REC_LIMIT, FINAL, PAGE = 8, 80, 40, 20
KINDS = ["node_crash", "load_spike", "service_crash", "cpu_pressure"]
B_SET = json.load(open(ROOT / "tuning/B_SETTINGS_PER_PLATFORM.json"))
C_PICK = json.load(open(ROOT / "tuning/LEAGUE_HELDOUT.json"))["omni_per_vessel"]
CANDS = candidates()
_cs = [ROOT / "tuning/CLOSURE_SEARCH2_DEV.json", ROOT / "tuning/CLOSURE_SEARCH_DEV.json"]
CLOSURE = next((json.load(open(p)) for p in _cs if p.exists()), {})
SL = dict(rho0=0.7, rho_min=0.7, kI=0.0, kE=0.0)


def plan(vessel, seed, level):
    rng = np.random.default_rng(seed * 10 + level)
    n_cl = 4 if vessel == "multi" else 1
    ev = []
    for _ in range(level):
        ev.append(dict(t=int(rng.integers(120, 1200)), ci=int(rng.integers(0, n_cl)), kind=KINDS[int(rng.integers(0, 4))],
                       dur=int(rng.integers(20, 81)), dur2=int(rng.integers(40, 161)), pick=float(rng.uniform())))
    return sorted(ev, key=lambda e: e["t"])


def injector(events, level):
    from fleet.sim import ALLOC
    by_t = {}
    for e in events:
        by_t.setdefault(e["t"], []).append(e)

    def on_tick(t, scn):
        for e in by_t.get(t, []):
            c = scn.clusters[e["ci"]]; p = c.pool
            if e["kind"] == "node_crash":
                p.nodes = max(0, p.nodes - max(1, int(math.floor(0.10 * level * p.nodes))))
            elif e["kind"] == "load_spike":
                for w in c.workloads:
                    w.demand[t:t + e["dur"]] *= (1.0 + 0.5 * level)
            elif e["kind"] == "service_crash":
                svc = [w for w in c.workloads if w.hpa] or c.workloads
                k = max(1, int(round(0.2 * level * len(svc))))
                start = int(e["pick"] * len(svc))
                for j in range(k):
                    w = svc[(start + j) % len(svc)]
                    if w.hpa:
                        w.replicas = max(1, w.replicas // 2)
                    w.backlog += 2.0 * float(w.demand[t])
            elif e["kind"] == "cpu_pressure":
                extra = 0.08 * level * p.nodes * p.cores * ALLOC / max(1, len(c.workloads))
                for w in c.workloads:
                    w.demand[t:t + e["dur2"]] += extra
    return on_tick


def arms(vessel):
    a = [("A", pl, pl, {}) for pl in PLATFORMS]
    a += [("B", pl, "omniB:" + pl, dict(b_law=BLaw(**B_SET[vessel][pl]))) for pl in PLATFORMS]
    pick = C_PICK[vessel]; cfg = CANDS[pick]
    if cfg is None:
        a.append(("C", "C-hpa", "omni_fleet", {}))
    else:
        a.append(("C", "C-hpa", "omni_speed", dict(speed_law=SpeedLaw(**cfg["law"]), omni_every=cfg["every"],
                                                     lat_gain=cfg["lat_gain"], slo_mult=cfg["slo_mult"])))
    cl = CLOSURE.get(vessel, {})
    a.append(("C", "C-strict", "omni_closure", dict(speed_law=SpeedLaw(**SL), omni_every=1,
                                                   direct_law=DirectLaw(**cl.get("direct", {})),
                                                   closure_law=ClosureLaw(**cl.get("closure", {})))))
    return a


def gauge(r, events):
    s = r["series"]
    ok = np.array([(x[0] <= R_LIM and x[1] < Q_LIM and x[2] <= PEND_LIM and x[3] <= P_LIM and x[4] < TH_LIM) for x in s])
    # run of in-basin ticks starting at each tick
    run = np.zeros(len(ok) + 1, int)
    for i in range(len(ok) - 1, -1, -1):
        run[i] = run[i + 1] + 1 if ok[i] else 0
    recs, unrec = [], 0
    for e in events:
        t0 = e["t"]
        hit = next((t for t in range(t0, len(ok)) if run[t] >= REC_OK or (run[t] > 0 and t + run[t] == len(ok))), None)
        if hit is None:
            recs.append(len(ok) - t0); unrec += 1
        else:
            recs.append(hit - t0)
    pages, i = 0, 0
    while i < len(ok):
        if not ok[i]:
            j = i
            while j < len(ok) and not ok[j]:
                j += 1
            pages += (j - i) >= PAGE; i = j
        else:
            i += 1
    conveyed = all(x <= REC_LIMIT for x in recs) and bool(ok[-FINAL:].all())
    mins = TICK / 60.0
    return {"conveyed": int(conveyed), "recovery_min": float(np.mean(recs)) * mins if recs else 0.0,
            "unrecovered": unrec, "first_conveyance_min": (float(np.argmax(run >= REC_OK)) * mins if (run >= REC_OK).any() else STEPS * mins),
            "persistence_min": float((~ok).sum()) * mins, "pages": pages,
            "max_latency_ms": float(max(x[0] for x in s)), "max_queue": float(max(x[1] for x in s)),
            "max_pending": float(max(x[2] for x in s)), "max_power": float(max(x[3] for x in s)),
            "timeouts": r["timeouts"], "work_completed": r["work_completed"], "energy_kwh": r["energy_kwh"],
            "p99_ms": r["p99_ms"], "start_stop": r["machines_started"] + r["machines_stopped"]}


def job(args):
    vessel, seed, level = args
    ev = plan(vessel, seed, level)
    sc = make_scenario(vessel, seed)
    rows = []
    for col, name, arm, kw in arms(vessel):
        r = sim_slo.run(sc, arm, on_tick=injector(ev, level), **kw)
        rows.append(dict(vessel=vessel, level=level, seed=seed, column=col, system=name, **gauge(r, ev)))
    return rows


GAUGES = ["conveyed", "recovery_min", "unrecovered", "persistence_min", "pages", "max_latency_ms", "max_queue",
          "max_pending", "timeouts", "work_completed", "energy_kwh", "p99_ms", "start_stop"]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    jobs = [(v, SEED0 + i, L) for v in VESSELS for L in LEVELS for i in range(n)]
    with Pool(4) as p:
        rows = [r for rs in p.imap_unordered(job, jobs, chunksize=4) for r in rs]
    rows.sort(key=lambda r: (r["vessel"], r["level"], r["seed"], r["column"], r["system"]))
    out = ROOT / "results/protocol"; out.mkdir(parents=True, exist_ok=True)
    with open(out / "raw_results.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
    summ = []
    for v in VESSELS:
        for L in LEVELS + ["all"]:
            for sysname in sorted({r["system"] for r in rows}, key=lambda s: (s.startswith("C"), s)):
                for col in ("A", "B", "C"):
                    rs = [r for r in rows if r["vessel"] == v and (L == "all" or r["level"] == L) and r["system"] == sysname and r["column"] == col]
                    if not rs:
                        continue
                    d = dict(vessel=v, level=L, column=col, system=sysname, runs=len(rs))
                    for g in GAUGES:
                        d[g] = float(np.sum([r[g] for r in rs])) if g in ("conveyed", "pages", "unrecovered") else float(np.mean([r[g] for r in rs]))
                    summ.append(d)
    with open(out / "summary_results.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(summ[0])); wr.writeheader(); wr.writerows(summ)
    (out / "PROTOCOL_SUMMARY.json").write_text(json.dumps({"runs_per_level": n, "seeds": [SEED0, SEED0 + n - 1],
                                                            "closure_settings": CLOSURE, "summary": summ}, indent=1))
    for d in summ:
        if d["level"] == "all":
            print(f"{d['vessel']:6} {d['column']} {d['system']:13} conveyed {int(d['conveyed']):4}/{d['runs']}  pages {int(d['pages']):5}  "
                  f"recovery {d['recovery_min']:6.1f} min  persist {d['persistence_min']:6.1f} min  timeouts {100*d['timeouts']:.2f}%  energy {d['energy_kwh']:.2f}")


if __name__ == "__main__":
    main()
