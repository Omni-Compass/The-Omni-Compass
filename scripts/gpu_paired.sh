#!/usr/bin/env bash
# One command on a machine with an NVIDIA GPU: native vs Omni-Compass watching vs Omni-Compass governing the GPU's
# power limit, measured by the device itself. Run as root (nvidia-smi -pl needs it). Needs python3 with torch (CUDA).
#
#   sudo bash scripts/gpu_paired.sh                  # 5 repetitions x 3 arms x 10 min (about 3 hours with idle gaps)
#   sudo REPS=5 DURATION=300 bash scripts/gpu_paired.sh   # shorter arms
#
# Each repetition runs the three arms back to back, order rotated. Each arm: COOLDOWN s idle, then the pinned workload
# (tools/gpu_workload.py: the same seeded stream of fp16 matrix-product requests every arm) for DURATION s plus DRAIN s,
# with nvidia-smi sampling power.draw, temperature and power.limit every SAMPLE_MS ms, and RAPL CPU package energy
# counters read at both ends where the machine has them.
#   native  no Omni process
#   watch   Omni runs and decides, and is forbidden to write (the control: any write fails the run)
#   omni    Omni writes the GPU power limit (omni_controller/gpu_governor.py --mode cap)
# The power limit is read once at the start (the snapshot). Every arm must begin and end at it; the kill switch restores
# it after the omni arm. The table (tools/gpu_reps.py) prints each gauge with its 95% interval; an interval that includes
# zero says not proven. Output: results/gpu/run-<UTC time>/ with every raw file and SHA256SUMS.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
REPS="${REPS:-5}"; DURATION="${DURATION:-600}"; DRAIN="${DRAIN:-30}"; COOLDOWN="${COOLDOWN:-60}"
GPU="${GPU:-0}"; SAMPLE_MS="${SAMPLE_MS:-200}"; INTERVAL="${INTERVAL:-5}"
SMI="${NVIDIA_SMI:-nvidia-smi}"; PY="${PYTHON:-python3}"
ARMS=(native watch omni)
PHASE="${PHASE:-smoke}"          # smoke: look, any n. confirm: preregistered, frozen, committed code, n from the prereg
if [ "$PHASE" = "confirm" ]; then REPS="${REPS_CONFIRM:-10}"; fi
export REPS DURATION DRAIN COOLDOWN SAMPLE_MS PHASE
OUT="${OUT:-results/gpu/run-$(date -u +%Y%m%dT%H%M%SZ)}"
WL_ARGS=${WORKLOAD_ARGS:-}
export TZ=UTC
mkdir -p "$OUT"

lim() { $SMI -i "$GPU" --query-gpu=power.limit --format=csv,noheader,nounits | tr -d ' '; }
rapl() {  # CPU package energy counters (microjoules), top-level packages only
  local f; for f in /sys/class/powercap/intel-rapl:[0-9]*/"$1"; do
    case "$f" in */intel-rapl:*:*/*) continue;; esac; if [ -r "$f" ]; then cat "$f"; fi; done 2>/dev/null | tr '\n' ' '
}

echo "== preflight"
command -v "$SMI" >/dev/null || { echo "nvidia-smi not found"; exit 1; }
$PY -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null || [ -n "${SIM:-}" ] \
  || { echo "python torch with CUDA not found (pip install torch)"; exit 1; }
START=$(lim); echo "$START" > "$OUT/snapshot.txt"
$SMI -i "$GPU" -pl "${START%.*}" >/dev/null || { echo "cannot set the power limit (run as root)"; exit 1; }
[ "$(lim)" = "$START" ] || { echo "power limit moved during preflight"; exit 1; }
$PY - "$OUT" "$GPU" "$START" <<'EOF'
import json, subprocess, sys, os
out, gpu, start = sys.argv[1:4]
smi = os.environ.get("NVIDIA_SMI", "nvidia-smi")
q = lambda f: subprocess.run([smi, "-i", gpu, f"--query-gpu={f}", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip()
r = {"gpus": gpu, "gpu_name": q("name"), "driver": q("driver_version"), "persistence": q("persistence_mode"),
     "power_limit_start_w": start, "power_limit_default_w": q("power.default_limit"), "power_limit_min_w": q("power.min_limit"),
     "power_limit_max_w": q("power.max_limit"), "reps": int(os.environ.get("REPS", 5)),
     "duration_s": float(os.environ.get("DURATION", 600)), "drain_s": float(os.environ.get("DRAIN", 30)),
     "cooldown_s": float(os.environ.get("COOLDOWN", 60)), "sample_ms": int(os.environ.get("SAMPLE_MS", 200)),
     "workload": "tools/gpu_workload.py (seeded fp16 matmul request stream)", "git": subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()}
open(f"{out}/receipt.json", "w").write(json.dumps(r, indent=1)); print(json.dumps(r))
EOF

freeze() {  # every file that decides or measures, hashed; the commit; whether any of them has uncommitted changes
  $PY - "$1" "$PHASE" <<'EOF'
import hashlib, json, subprocess, sys
files = ["omni_controller/gpu_governor.py", "omni_controller/muscles.py", "omnicompass/adapter.py", "omnicompass/core.py",
         "tools/gpu_workload.py", "tools/gpu_reps.py", "scripts/gpu_paired.sh", "docs/GPU_PREREGISTRATION.md"]
h = {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}
git = ["git", "-c", "safe.directory=*"]   # run as root on a clone the login user owns
st = subprocess.run(git + ["status", "--porcelain", "--"] + files, capture_output=True, text=True)
head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True)
# git unreadable counts as uncommitted: a freeze I cannot check is not a freeze
r = {"phase": sys.argv[2], "commit": head.stdout.strip(), "dirty": bool(st.stdout.strip()) or st.returncode != 0 or head.returncode != 0,
     "git_error": (st.stderr + head.stderr).strip()[:300], "files": h}
open(sys.argv[1], "w").write(json.dumps(r, indent=1))
EOF
}
freeze "$OUT/FREEZE.json"
if [ "$PHASE" = "confirm" ] && grep -q '"dirty": true' "$OUT/FREEZE.json"; then
  echo "confirmation phase refuses uncommitted Omni code: commit it first, then run (FREEZE.json lists the files)"; exit 1
fi

echo "== calibrate the workload at the start limit (once, for every arm)"
$PY tools/gpu_workload.py calibrate --out "$OUT" --device "cuda:$GPU" ${SIM:+--sim} $WL_ARGS
SERVICE_MS=$($PY -c "import json;print(json.load(open('$OUT/calib.json'))['service_ms'])")
SLO_MS="${SLO_MS:-$($PY -c "print(round(10*$SERVICE_MS,1))")}"   # response-time target: ten bare service times
echo "service time ${SERVICE_MS} ms, response-time target ${SLO_MS} ms" | tee "$OUT/slo.txt"

fail=0
for rep in $(seq 1 "$REPS"); do
  k=$(( (rep - 1) % 3 )); order=("${ARMS[@]:$k}" "${ARMS[@]:0:$k}")
  for arm in "${order[@]}"; do
    D="$OUT/rep-$rep/$arm"; mkdir -p "$D"
    echo "== rep $rep, arm $arm"
    if [ "$(lim)" != "$START" ]; then echo "limit $(lim) != start $START before the arm"; $SMI -i "$GPU" -pl "${START%.*}"; fail=1; fi
    sleep "$COOLDOWN"
    lim > "$D/limit_start.txt"
    $SMI --query-gpu=timestamp,index,power.draw,temperature.gpu,utilization.gpu,power.limit,clocks.sm \
      --format=csv,noheader,nounits -lms "$SAMPLE_MS" > "$D/smi.csv" 2>"$D/smi.err" &
    smi_pid=$!
    rapl energy_uj > "$D/rapl_start.txt"; rapl max_energy_range_uj > "$D/rapl_range.txt"
    date -u +%s.%N > "$D/window_start.txt"
    gov_pid=""
    if [ "$arm" != "native" ]; then
      mode=watch; [ "$arm" = "omni" ] && mode=cap
      rm -f "$D/kill"
      $PY -m omni_controller.gpu_governor --mode "$mode" --gpus "$GPU" --smi "$SMI" --interval "$INTERVAL" \
        --audit "$D/audit.jsonl" --kill-file "$D/kill" --latency-file "$D/latency.csv" --slo-ms "$SLO_MS" \
        > "$D/governor.log" 2>&1 &
      gov_pid=$!
    fi
    $PY tools/gpu_workload.py run --calib-file "$OUT/calib.json" --out "$D" --device "cuda:$GPU" \
      --duration "$DURATION" --drain "$DRAIN" > "$D/workload.log" 2>&1
    date -u +%s.%N > "$D/window_end.txt"
    rapl energy_uj > "$D/rapl_end.txt"
    if [ -n "$gov_pid" ]; then
      touch "$D/kill"; wait "$gov_pid" && echo 0 > "$D/governor_exit.txt" || echo $? > "$D/governor_exit.txt"
    fi
    kill "$smi_pid" 2>/dev/null || true; wait "$smi_pid" 2>/dev/null || true
    lim > "$D/limit_end.txt"
    if [ "$(cat "$D/limit_end.txt")" != "$START" ]; then
      echo "limit not restored after $arm: $(cat "$D/limit_end.txt") != $START"; $SMI -i "$GPU" -pl "${START%.*}"; fail=1
    fi
  done
done

freeze "$OUT/FREEZE_END.json"
echo "== table"
set +e; $PY tools/gpu_reps.py "$OUT"; rc=$?; set -e
(cd "$OUT" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
echo "raw files and checksums: $OUT"
[ "$fail" = 0 ] && [ "$rc" = 0 ] || { echo "RUN INVALID (see GPU_REPS.md)"; exit 2; }
