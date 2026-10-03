#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Real AI serving for the GPU bench: a language model served by vLLM (OpenAI-compatible server on this machine), asked
the same seeded stream of prompts in every arm, so the card's firmware alone and the firmware with Omni-Compass on top
get exactly the same requests at exactly the same moments.

Each request asks for exactly --tokens new tokens (ignore_eos), so every request is the same amount of work. It writes
the three files the bench reads (scripts/gpu_paired.sh, WORKLOAD_CMD):
  latency.csv   elapsed_seconds, latency_ms, ok, service_ms   one row per finished request (service_ms: the request's
                time in the server, which on a batching server is its time to finish)
  requests.csv  arrival_s, start_s, done_s, latency_ms, ok
  summary.json  requests, served, not served, t0_epoch, tokens per request, the model

  calibrate   time --calib requests one at a time; writes calib.json (service_ms: the median, the bench's response line
              is ten times it)
  run         serve the schedule for --duration seconds (Poisson arrivals at --rate per second), then --drain seconds

Tokens per second = requests served x --tokens / duration; the bench's work per energy is requests per kJ, so tokens
per kJ is that times --tokens.
"""
from __future__ import annotations

import argparse, json, os, random, threading, time, urllib.request
from pathlib import Path


def ask(url, model, prompt, tokens, timeout):
    body = json.dumps({"model": model, "prompt": prompt, "max_tokens": tokens, "temperature": 0.0,
                       "ignore_eos": True}).encode()
    req = urllib.request.Request(url + "/v1/completions", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    return out["usage"]["completion_tokens"]


PROMPT = "Explain in plain words how a thermostat keeps a room at a steady temperature, step by step."


def calibrate(a):
    ts = []
    for _ in range(a.calib):
        t = time.perf_counter(); ask(a.url, a.model, PROMPT, a.tokens, 120); ts.append((time.perf_counter() - t) * 1000.0)
    ts.sort()
    c = {"service_ms": ts[len(ts) // 2], "tokens": a.tokens, "model": a.model, "rate": a.rate, "seed": a.seed}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "calib.json").write_text(json.dumps(c, indent=1)); print(json.dumps(c))


def run(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    sched, t = [], 0.0
    while True:
        t += rng.expovariate(a.rate)
        if t >= a.duration:
            break
        sched.append(t)
    lat = open(out / "latency.csv", "w"); lat.write("elapsed_seconds,latency_ms,ok,service_ms\n"); lat.flush()
    rows, lock = [], threading.Lock()
    t0, t0_epoch, end = time.perf_counter(), time.time(), a.duration + a.drain

    def one(arr):
        start = time.perf_counter() - t0
        try:
            got = ask(a.url, a.model, PROMPT, a.tokens, max(1.0, end - start))
            done = time.perf_counter() - t0
            ok = 1 if got == a.tokens and done <= end else 0
        except Exception:  # noqa: BLE001  a failed or timed-out request is not served
            done, ok = time.perf_counter() - t0, 0
        ms = (done - arr) * 1000.0
        with lock:
            rows.append((arr, start, done, ms, ok))
            if ok:
                lat.write(f"{done:.3f},{ms:.3f},1,{(done - start) * 1000.0:.3f}\n"); lat.flush()

    threads = []
    for arr in sched:
        w = arr - (time.perf_counter() - t0)
        if w > 0:
            time.sleep(w)
        th = threading.Thread(target=one, args=(arr,), daemon=True); th.start(); threads.append(th)
    for th in threads:
        th.join(timeout=max(0.0, end - (time.perf_counter() - t0)) + 5.0)
    left = end - (time.perf_counter() - t0)
    if left > 0:
        time.sleep(left)
    with lock:
        done_rows = list(rows)
    served = sum(1 for r in done_rows if r[4] == 1)
    with open(out / "requests.csv", "w") as f:
        f.write("arrival_s,start_s,done_s,latency_ms,ok\n")
        for r in sorted(done_rows):
            f.write(",".join(f"{v:.4f}" if isinstance(v, float) else str(v) for v in r) + "\n")
    s = {"requests": len(sched), "served": served, "not_served": len(sched) - served, "duration_s": a.duration,
         "drain_s": a.drain, "t0_epoch": t0_epoch, "tokens_per_request": a.tokens, "model": a.model, "rate": a.rate,
         "seed": a.seed, "tokens_per_second": served * a.tokens / a.duration}
    (out / "summary.json").write_text(json.dumps(s, indent=1)); print(json.dumps(s))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["calibrate", "run"])
    ap.add_argument("--out", default=os.environ.get("OUT_DIR", "llm_run"))
    ap.add_argument("--url", default=os.environ.get("LLM_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"))
    ap.add_argument("--tokens", type=int, default=128)
    ap.add_argument("--rate", type=float, default=float(os.environ.get("LLM_RATE", 4.0)))
    ap.add_argument("--seed", type=int, default=20261003)
    ap.add_argument("--calib", type=int, default=10)
    ap.add_argument("--duration", type=float, default=float(os.environ.get("DURATION", 600)))
    ap.add_argument("--drain", type=float, default=float(os.environ.get("DRAIN", 30)))
    a = ap.parse_args(argv)
    calibrate(a) if a.cmd == "calibrate" else run(a)


if __name__ == "__main__":
    main()
