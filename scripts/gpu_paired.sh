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
# Three receipts, kept apart: A the governor's audit.jsonl (telemetry, six-state reading, command, shield), B its
# actuator records (requested, return code, read-back, enforced limit, delay), C the bench's own nvidia-smi sampling
# and the workload's requests.csv (Omni never supplies its own outcome). Refused unless power management is Enabled.
# The power limit is read once at the start (the snapshot). Every arm must begin and end at it; the kill switch restores
# it after the omni arm. The table (tools/gpu_reps.py) prints each gauge with its 95% interval; an interval that includes
# zero says not proven. Output: results/gpu/run-<UTC time>/ with every raw file and SHA256SUMS.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
REPS="${REPS:-5}"; DURATION="${DURATION:-600}"; DRAIN="${DRAIN:-30}"; COOLDOWN="${COOLDOWN:-60}"
GPU="${GPU:-0}"; SAMPLE_MS="${SAMPLE_MS:-200}"; INTERVAL="${INTERVAL:-2}"
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
q1() { $SMI -i "$GPU" --query-gpu="$1" --format=csv,noheader,nounits 2>/dev/null | tr -d ' '; }
devmeter() {  # the card's own energy counter (NVML total energy, millijoules, Volta and newer) and its health counters:
  # a cross-check on the integrated power.draw and a record of wear, read by the bench only. "unavailable" where absent.
  local e; e=$($PY -c "import pynvml as n; n.nvmlInit(); print(n.nvmlDeviceGetTotalEnergyConsumption(n.nvmlDeviceGetHandleByIndex($GPU)))" 2>/dev/null || true)
  echo "energy_mj ${e:-unavailable}"
  local f; for f in ecc.errors.uncorrected.volatile.total ecc.errors.corrected.volatile.total retired_pages.pending clocks_event_reasons.hw_thermal_slowdown; do
    echo "$f $(q1 "$f" || true)"; done
}
rapl() {  # RAPL counters by domain name: "<domain dir> <name> <energy_uj> <max_energy_range_uj>" per line.
  # package-N and dram are summed by the table separately; psys (platform) is recorded, never added to them
  # (package already contains the cores and uncore; psys is a wider, vendor-defined scope). Omni never reads these.
  local d n; for d in "${RAPL_ROOT:-/sys/class/powercap}"/intel-rapl:*; do
    [ -r "$d/energy_uj" ] || continue; n=$(cat "$d/name" 2>/dev/null || echo unknown)
    case "$n" in package-*|dram|psys) echo "$(basename "$d") $n $(cat "$d/energy_uj") $(cat "$d/max_energy_range_uj" 2>/dev/null || echo 0)";; esac
  done 2>/dev/null
}

echo "== preflight"
command -v "$SMI" >/dev/null || { echo "nvidia-smi not found"; exit 1; }
$PY -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null || [ -n "${SIM:-}" ] \
  || { echo "python torch with CUDA not found (pip install torch)"; exit 1; }
START=$(lim); echo "$START" > "$OUT/snapshot.txt"
# the card obeys enforced.power.limit; the bench samples it where the driver reports it, and the clock-limit reasons
SMI_FIELDS="timestamp,index,power.draw,temperature.gpu,utilization.gpu,power.limit,clocks.sm"
ENFORCED=$(q1 enforced.power.limit || true)
if [ -n "$ENFORCED" ] && [ "${ENFORCED#[}" = "$ENFORCED" ]; then SMI_FIELDS="$SMI_FIELDS,enforced.power.limit"; else ENFORCED=unsupported; fi
for f in clocks_event_reasons.active clocks_throttle_reasons.active; do
  v=$(q1 "$f" || true); if [ -n "$v" ] && [ "${v#[}" = "$v" ]; then SMI_FIELDS="$SMI_FIELDS,$f"; break; fi
done
echo "$SMI_FIELDS" > "$OUT/smi_fields.txt"
# the declared envelope (the buyer's box): lowest watts and response-time target, declared before any trial. The
# highest watts are the snapshot limit. A confirmation run refuses to start without it.
ENV_FLOOR_W=0
if [ -n "${ENVELOPE:-}" ]; then
  [ -r "$ENVELOPE" ] || { echo "ENVELOPE file $ENVELOPE unreadable"; exit 1; }
  read -r ENV_FLOOR_W ENV_SLO < <($PY -c "import json,sys; e=json.load(open(sys.argv[1])); print(float(e['power_min_w']), float(e.get('slo_ms', 0)))" "$ENVELOPE") \
    || { echo "ENVELOPE must hold power_min_w (and optionally slo_ms)"; exit 1; }
  DEVMIN=$(q1 power.min_limit); $PY -c "import sys; f,lo,hi=map(float,sys.argv[1:4]); sys.exit(0 if lo<=f<=hi else 1)" "$ENV_FLOOR_W" "$DEVMIN" "$START" \
    || { echo "envelope floor $ENV_FLOOR_W W outside the device range [$DEVMIN, $START] W"; exit 1; }
  cp "$ENVELOPE" "$OUT/envelope.json"
  if [ "${ENV_SLO%.*}" != "0" ] && [ -z "${SLO_MS:-}" ]; then SLO_MS="$ENV_SLO"; fi
elif [ "$PHASE" = "confirm" ]; then
  echo "confirmation refuses to start without a declared envelope: ENVELOPE=file.json with power_min_w (and slo_ms)"; exit 1
fi
MGMT=$(q1 power.management || true)
[ "$MGMT" = "Enabled" ] || { echo "power management is '${MGMT:-unsupported}', not Enabled: a written limit would not bind"; exit 1; }
$SMI -i "$GPU" -pl "${START%.*}" >/dev/null || { echo "cannot set the power limit (run as root)"; exit 1; }
[ "$(lim)" = "$START" ] || { echo "power limit moved during preflight"; exit 1; }
$PY - "$OUT" "$GPU" "$START" <<'EOF'
import json, subprocess, sys, os
out, gpu, start = sys.argv[1:4]
smi = os.environ.get("NVIDIA_SMI", "nvidia-smi")
q = lambda f: subprocess.run([smi, "-i", gpu, f"--query-gpu={f}", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip()
r = {"gpus": gpu, "gpu_name": q("name"), "driver": q("driver_version"), "persistence": q("persistence_mode"),
     "power_management": q("power.management"), "power_limit_enforced_w": q("enforced.power.limit") or "unsupported",
     "gpu_uuid": q("uuid"), "gpu_serial": q("serial"), "vbios": q("vbios_version"), "kernel": os.uname().release, "host": os.uname().nodename,
     "power_limit_start_w": start, "power_limit_default_w": q("power.default_limit"), "power_limit_min_w": q("power.min_limit"),
     "power_limit_max_w": q("power.max_limit"), "reps": int(os.environ.get("REPS", 5)),
     "duration_s": float(os.environ.get("DURATION", 600)), "drain_s": float(os.environ.get("DRAIN", 30)),
     "cooldown_s": float(os.environ.get("COOLDOWN", 60)), "sample_ms": int(os.environ.get("SAMPLE_MS", 200)),
     "workload": "tools/gpu_workload.py (seeded fp16 matmul request stream)",
     "workload_sha256": __import__("hashlib").sha256(open("tools/gpu_workload.py", "rb").read()).hexdigest(),
     "workload_cmd": os.environ.get("WORKLOAD_CMD", ""),
     "envelope": json.load(open(f"{out}/envelope.json")) if os.path.exists(f"{out}/envelope.json") else None,
     "mechanism_id": subprocess.run([sys.executable, "tools/mechanism_identity.py", "--id"], capture_output=True, text=True).stdout.strip(),
     "git": subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()}
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

if [ -n "${WALL_METER:-}" ]; then
  # the whole machine at the wall, from a smart plug Omni never reads (tools/wall_meter.py)
  w=$($PY tools/wall_meter.py "$WALL_METER" --once) || { echo "wall meter $WALL_METER unreadable"; exit 1; }
  echo "wall meter ${WALL_METER%%:*} reads $w W" | tee "$OUT/wall_meter.txt"
fi

if [ -n "${WORKLOAD_CMD:-}" ]; then
  # any workload (vLLM, TensorRT-LLM, an MLPerf inference harness): run once per arm with OUT_DIR, DURATION, DRAIN
  # and DEVICE in its environment; it must write OUT_DIR/latency.csv live and requests.csv and summary.json at the end
  # in tools/gpu_workload.py's format. Its own response-time target is required.
  [ -n "${SLO_MS:-}" ] || { echo "WORKLOAD_CMD needs SLO_MS (the workload's response-time target)"; exit 1; }
  echo "$WORKLOAD_CMD" > "$OUT/workload_cmd.txt"
else
  echo "== calibrate the workload at the start limit (once, for every arm)"
  $PY tools/gpu_workload.py calibrate --out "$OUT" --device "cuda:$GPU" ${SIM:+--sim} $WL_ARGS
  SERVICE_MS=$($PY -c "import json;print(json.load(open('$OUT/calib.json'))['service_ms'])")
  SLO_MS="${SLO_MS:-$($PY -c "print(round(10*$SERVICE_MS,1))")}"   # response-time target: ten bare service times
fi
echo "service time ${SERVICE_MS:-set by the workload} ms, response-time target ${SLO_MS} ms" | tee "$OUT/slo.txt"

fail=0
# REP_ONLY=k runs repetition k alone (its rotation included): one repetition per machine when repetitions are spread
# over several machines of one type; the three arms of a repetition always share one machine
for rep in ${REP_ONLY:-$(seq 1 "$REPS")}; do
  k=$(( (rep - 1) % 3 )); order=("${ARMS[@]:$k}" "${ARMS[@]:0:$k}")
  for arm in "${order[@]}"; do
    D="$OUT/rep-$rep/$arm"; mkdir -p "$D"
    echo "== rep $rep, arm $arm"
    if [ "$(lim)" != "$START" ]; then echo "limit $(lim) != start $START before the arm"; $SMI -i "$GPU" -pl "${START%.*}"; fail=1; fi
    sleep "$COOLDOWN"
    lim > "$D/limit_start.txt"
    cp "$OUT/smi_fields.txt" "$D/smi_fields.txt"
    $SMI --query-gpu="$SMI_FIELDS" --format=csv,noheader,nounits -lms "$SAMPLE_MS" > "$D/smi.csv" 2>"$D/smi.err" &
    smi_pid=$!
    wall_pid=""
    if [ -n "${WALL_METER:-}" ]; then $PY tools/wall_meter.py "$WALL_METER" "$D/wall.csv" 2>"$D/wall.err" & wall_pid=$!; sleep 2; fi
    rapl > "$D/rapl_start.tsv"
    devmeter > "$D/device_start.txt"
    date -u +%s.%N > "$D/window_start.txt"
    gov_pid=""
    if [ "$arm" != "native" ]; then
      mode=watch; [ "$arm" = "omni" ] && mode=cap
      rm -f "$D/kill"
      $PY -m omni_controller.gpu_governor --mode "$mode" --gpus "$GPU" --smi "$SMI" --interval "$INTERVAL" \
        --audit "$D/audit.jsonl" --kill-file "$D/kill" --latency-file "$D/latency.csv" --slo-ms "$SLO_MS" --floor-w "$ENV_FLOOR_W" \
        > "$D/governor.log" 2>&1 &
      gov_pid=$!
    fi
    if [ -n "${WORKLOAD_CMD:-}" ]; then
      OUT_DIR="$D" DEVICE="cuda:$GPU" bash -c "$WORKLOAD_CMD" > "$D/workload.log" 2>&1 || echo "workload exited $?" >> "$D/workload.log"
    else
      $PY tools/gpu_workload.py run --calib-file "$OUT/calib.json" --out "$D" --device "cuda:$GPU" \
        --duration "$DURATION" --drain "$DRAIN" > "$D/workload.log" 2>&1
    fi
    date -u +%s.%N > "$D/window_end.txt"
    devmeter > "$D/device_end.txt"
    rapl > "$D/rapl_end.tsv"
    [ -n "$wall_pid" ] && { kill "$wall_pid" 2>/dev/null || true; wait "$wall_pid" 2>/dev/null || true; }
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
# each repetition carries its machine's own record, so repetitions from several machines can be pooled
for r in "$OUT"/rep-*; do
  for f in receipt.json snapshot.txt smi_fields.txt envelope.json calib.json workload_cmd.txt slo.txt FREEZE.json FREEZE_END.json wall_meter.txt; do
    [ -f "$OUT/$f" ] && cp "$OUT/$f" "$r/$f"
  done
done
echo "== table"
set +e; $PY tools/gpu_reps.py "$OUT"; rc=$?; set -e
(cd "$OUT" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
echo "raw files and checksums: $OUT"
[ "$fail" = 0 ] && [ "$rc" = 0 ] || { echo "RUN INVALID (see GPU_REPS.md)"; exit 2; }
