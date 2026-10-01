#!/usr/bin/env bash
# The whole GPU test on a rented NVIDIA machine, one command (docs/GPU_RUN_GUIDE.md, section C):
#
#   sudo bash scripts/gpu_rented_run.sh
#
# 1. checks the machine (NVIDIA GPU, root, PyTorch with CUDA, power management Enabled);
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
$SMI -i "$GPU" --query-gpu=name,driver_version,power.limit,power.min_limit,power.management --format=csv,noheader
$PY -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null || [ -n "${SIM:-}" ] \
  || { echo "PyTorch with CUDA not found: pip install torch, or rent an image that has it"; exit 1; }
[ -z "$(git status --porcelain -- omni_controller omnicompass tools scripts docs/GPU_PREREGISTRATION.md 2>/dev/null)" ] \
  || { echo "the code has local changes: the confirmation runs only on committed code (git stash, or a fresh clone)"; exit 1; }

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
PACK=("results/gpu/smoke-$STAMP" "$ENVELOPE")
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
