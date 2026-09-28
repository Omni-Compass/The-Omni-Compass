"""The pinned GPU workload for scripts/gpu_paired.sh: a fixed stream of inference-like requests served by one GPU.

Each request is --iters fp16 matrix products of size --n x --n on the GPU (synchronised, so its time is the GPU's time).
Requests arrive open-loop on a schedule fixed by --seed: Poisson arrivals whose rate steps through --phases, each phase a
share of the GPU's own capacity measured by `calibrate` at full power before any arm runs. Every arm therefore receives
exactly the same requests at exactly the same moments; what differs is only how the GPU is governed.

  calibrate  times --calib requests back to back at the current (start) power limit and writes calib.json:
             iters (chosen so one request takes about --target-ms), service_ms, and every setting below
  run        serves the schedule for --duration seconds, then --drain seconds for requests still queued, and writes
             latency.csv  (elapsed_seconds, latency_ms, ok)  live, one row per finished request
             requests.csv (arrival_s, start_s, done_s, latency_ms, ok)
             summary.json (requests, served, not served, t0_epoch: the wall clock at time 0, the settings)
Any other workload (vLLM, TensorRT-LLM, an MLPerf inference harness) plugs into the bench through WORKLOAD_CMD
(scripts/gpu_paired.sh) by writing the same three files; tools/gpu_reps.py checks them.
             A request still queued when the drain ends is not served (ok = 0).
--sim replaces the GPU by a sleep of service_ms (for the harness's own tests on machines without a GPU).
"""
from __future__ import annotations

import argparse, json, queue, random, sys, threading, time
from pathlib import Path


def gpu_kernel(n, device):
    import torch
    a = torch.randn(n, n, device=device, dtype=torch.float16)
    b = torch.randn(n, n, device=device, dtype=torch.float16)

    def run(iters):
        for _ in range(iters):
            torch.matmul(a, b)
        torch.cuda.synchronize(device)
    run(3)
    return run


def sim_kernel(service_ms):
    def run(iters):
        time.sleep(service_ms / 1000.0 * iters / 10.0)
    return run


def calibrate(a):
    run = sim_kernel(a.sim_ms) if a.sim else gpu_kernel(a.n, a.device)
    iters = 10
    t = time.perf_counter(); run(iters); one = (time.perf_counter() - t) * 1000.0
    iters = max(1, round(iters * a.target_ms / max(one, 1e-3)))
    ts = []
    for _ in range(a.calib):
        t = time.perf_counter(); run(iters); ts.append((time.perf_counter() - t) * 1000.0)
    ts.sort()
    c = {"iters": iters, "service_ms": ts[len(ts) // 2], "n": a.n, "seed": a.seed, "phases": a.phases,
         "target_ms": a.target_ms, "sim": bool(a.sim)}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "calib.json").write_text(json.dumps(c, indent=1))
    print(json.dumps(c))


def arrivals(c, duration):
    """The fixed schedule: Poisson arrivals, rate = phase share / service time, from the seed alone."""
    rng = random.Random(c["seed"])
    shares = [float(x) for x in str(c["phases"]).split(",")]
    per = duration / len(shares)
    out, t = [], 0.0
    for i, f in enumerate(shares):
        rate = f / (c["service_ms"] / 1000.0)
        t = max(t, i * per)
        while True:
            t += rng.expovariate(rate)
            if t >= (i + 1) * per:
                t = (i + 1) * per
                break
            out.append(t)
    return out


def serve(a):
    c = json.loads(Path(a.calib_file).read_text())
    run = sim_kernel(c["service_ms"] * 10.0 / c["iters"]) if c["sim"] else gpu_kernel(c["n"], a.device)
    sched = arrivals(c, a.duration)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    lat = open(out / "latency.csv", "w"); lat.write("elapsed_seconds,latency_ms,ok\n"); lat.flush()
    q, rows, t0 = queue.Queue(), [], time.perf_counter()
    t0_epoch = time.time()                   # the wall clock at t0, so the bench can line requests up with its meters
    end = a.duration + a.drain

    def worker():
        while True:
            arr = q.get()
            if arr is None:
                return
            now = time.perf_counter() - t0
            if now >= end:
                rows.append((arr, None, None, None, 0)); continue
            run(c["iters"])
            done = time.perf_counter() - t0
            ms = (done - arr) * 1000.0
            rows.append((arr, now, done, ms, 1))
            lat.write(f"{done:.3f},{ms:.3f},1\n"); lat.flush()

    th = threading.Thread(target=worker, daemon=True); th.start()
    for arr in sched:
        wait = arr - (time.perf_counter() - t0)
        if wait > 0:
            time.sleep(wait)
        q.put(arr)
    q.put(None)
    th.join(timeout=max(0.0, end - (time.perf_counter() - t0)) + 5.0)
    left = end - (time.perf_counter() - t0)
    if left > 0:
        time.sleep(left)                     # every arm is measured over the same window length
    served = sum(1 for r in rows if r[4] == 1)
    with open(out / "requests.csv", "w") as f:
        f.write("arrival_s,start_s,done_s,latency_ms,ok\n")
        for r in rows:
            f.write(",".join("" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v)) for v in r) + "\n")
    s = {"requests": len(sched), "served": served, "not_served": len(sched) - served, "duration_s": a.duration, "t0_epoch": t0_epoch,
         "drain_s": a.drain, **{k: c[k] for k in ("iters", "service_ms", "n", "seed", "phases", "sim")}}
    (out / "summary.json").write_text(json.dumps(s, indent=1))
    print(json.dumps(s))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["calibrate", "run"])
    ap.add_argument("--out", default="gpu_run")
    ap.add_argument("--calib-file", default="")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--n", type=int, default=4096)
    ap.add_argument("--target-ms", type=float, default=50.0)
    ap.add_argument("--calib", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--phases", default="0.3,0.6,0.8,0.3,0.6,0.3", help="shares of full-power capacity, one per phase")
    ap.add_argument("--duration", type=float, default=600.0)
    ap.add_argument("--drain", type=float, default=30.0)
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--sim-ms", type=float, default=20.0)
    a = ap.parse_args(argv)
    calibrate(a) if a.cmd == "calibrate" else serve(a)


if __name__ == "__main__":
    main()
