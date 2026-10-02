#!/usr/bin/env bash
# The whole GPU test on a rented NVIDIA machine, one command (docs/GPU_RUN_GUIDE.md, section C):
#
#   sudo bash scripts/gpu_rented_run.sh
#
# 1. checks the machine (NVIDIA GPU, root, PyTorch with CUDA, power management Enabled), then the wire check
#    (tools/gpu_wire_check.py: both of the card's wires follow, read back and go home);
# 2. declares the envelope before any trial (docs/GPU_PREREGISTRATION.md, amendment 3): lowest watts =
#    max(device minimum, 70% of the limit read now), unless ENVELOPE=file.json is given;
# 3. smoke: 3 repetitions x 3 arms x 180 s (about 40 minutes). It checks the wiring on real hardware. It never counts;
# 4. if smoke is valid: the preregistered confirmation, 10 repetitions x 3 arms x 600 s (about 6 hours), on the same
#    committed code (STOP_AFTER_SMOKE=1 stops after step 3);
# 5. packs both result folders into one file to send back, and prints the label the table chose by rule.
set -euo pipefail
cd "$(dirname "$0")/.."
SMI="${NVIDIA_SMI:-nvidia-smi}"; PY="${PYTHON:-python3}"; GPU="${GPU:-0}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p results/gpu

echo "== checking the machine"
[ "$(id -u)" = 0 ] || [ -n "${SIM:-}" ] || { echo "run with sudo: setting the power limit needs root"; exit 1; }
command -v "$SMI" >/dev/null || { echo "nvidia-smi not found: this machine has no NVIDIA driver"; exit 1; }
# one copy only: two copies on one card write the same power limit and every arm of both is invalid (amendment 4)
exec 9>"${LOCK:-/tmp/omni-gpu-bench.lock}"
flock -n 9 || { echo "another copy of this test is already running on this machine. Start it once only: wait for it to finish (or reboot the machine), then run this one command again."; exit 1; }
BUSY=$($SMI -i "$GPU" --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null || true)
[ -z "$BUSY" ] || { echo "something else is using the GPU, so the test would not be measuring only itself:"; echo "$BUSY"; echo "stop it (or reboot the machine), then run this one command again."; exit 1; }
# every run starts from the card's own default limit, not from whatever an earlier or aborted run left behind
DEF=$($SMI -i "$GPU" --query-gpu=power.default_limit --format=csv,noheader,nounits | tr -d ' ')
[ -n "${SIM:-}" ] || $SMI -i "$GPU" -pl "${DEF%.*}" >/dev/null || { echo "cannot set the default power limit $DEF W"; exit 1; }
echo "power limit reset to the card's default: $DEF W"
[ -n "${SIM:-}" ] || $SMI -i "$GPU" -rgc >/dev/null 2>&1 || true
echo "clock range reset to the card's own"
$SMI -i "$GPU" --query-gpu=name,driver_version,power.limit,power.min_limit,power.management --format=csv,noheader
$PY -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null || [ -n "${SIM:-}" ] \
  || { echo "PyTorch with CUDA not found: pip install torch, or rent an image that has it"; exit 1; }
# run as root on a clone the login user owns, so git is told the directory is safe; unreadable git refuses the run
GITST=$(git -c safe.directory='*' status --porcelain -- omni_controller omnicompass tools scripts docs/GPU_PREREGISTRATION.md) \
  || { echo "git cannot read this clone: run from a fresh git clone of the repository"; exit 1; }
[ -z "$GITST" ] || { echo "the code has local changes: the confirmation runs only on committed code (git stash, or a fresh clone)"; exit 1; }
echo "code: commit $(git -c safe.directory='*' rev-parse --short HEAD), unchanged"

echo "== wire check (both wires follow, read back and go home; nothing runs if this fails)"
$PY tools/gpu_wire_check.py --gpu "$GPU" --smi "$SMI" | tee "results/gpu/wirecheck-$STAMP.txt"
[ "${PIPESTATUS[0]}" = 0 ] || { echo "WIRE CHECK FAILED: send results/gpu/wirecheck-$STAMP.txt back; nothing else was run."; exit 1; }

if [ -z "${ENVELOPE:-}" ]; then
  ENVELOPE="results/gpu/envelope-$STAMP.json"
  $PY tools/declare_envelope.py "$ENVELOPE" --gpu "$GPU" --smi "$SMI"
fi
export ENVELOPE

echo "== smoke (wiring check on real hardware; never counted)"
set +e
PHASE=smoke REPS="${SMOKE_REPS:-3}" DURATION="${SMOKE_DURATION:-180}" COOLDOWN="${SMOKE_COOLDOWN:-30}" \
  OUT="results/gpu/smoke-$STAMP" bash scripts/gpu_paired.sh
smoke_rc=$?
set -e
PACK=("results/gpu/smoke-$STAMP" "$ENVELOPE" "results/gpu/wirecheck-$STAMP.txt")
if [ "$smoke_rc" != 0 ]; then
  echo "SMOKE INVALID (exit $smoke_rc): the wiring needs a fix before any confirmation. Send the packed file back."
elif [ -n "${STOP_AFTER_SMOKE:-}" ]; then
  echo "smoke valid; stopping as asked (STOP_AFTER_SMOKE)."
else
  echo "== confirmation (preregistered: 10 repetitions, 600 s per arm, frozen code)"
  set +e
  PHASE=confirm OUT="results/gpu/run-$STAMP" bash scripts/gpu_paired.sh
  confirm_rc=$?
  set -e
  PACK+=("results/gpu/run-$STAMP")
  $PY -c "import json,sys; h=json.load(open(sys.argv[1])).get('headline',{}); print('RESULT, BY RULE:', h.get('verdict','(no verdict)'))" \
    "results/gpu/run-$STAMP/GPU_REPS.json" 2>/dev/null || echo "no table produced (exit $confirm_rc)"
fi
tar czf "results/gpu/omni-gpu-$STAMP.tar.gz" "${PACK[@]}"
echo "== send this one file back: results/gpu/omni-gpu-$STAMP.tar.gz"
