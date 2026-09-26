"""Real response-time gauge: time HTTP requests to a URL every INTERVAL seconds; append elapsed,ms,ok to OUT."""
import os, sys, time, urllib.request
url, out = sys.argv[1], sys.argv[2]
interval, duration, n = float(os.environ.get("INTERVAL", "5")), float(os.environ.get("DURATION", "1200")), int(os.environ.get("N", "5"))
t0 = time.time()
with open(out, "w") as f:
    f.write("elapsed_seconds,latency_ms,ok\n")
    while time.time() - t0 < duration:
        for _ in range(n):
            s = time.time(); ok = 1
            try:
                urllib.request.urlopen(url, timeout=10).read()
            except Exception:
                ok = 0
            f.write(f"{time.time() - t0:.1f},{1000 * (time.time() - s):.1f},{ok}\n")
        f.flush(); time.sleep(interval)
