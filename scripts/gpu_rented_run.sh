#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
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
#    committed code (STOP_AFTER_SMOKE=1 stops after step 3), on the pinned compute-bound workload (matrix products);
# 5. the second preregistered confirmation, the same 10 x 3 x 600 s on AI token generation (the decode workload:
#    every weight streamed from memory once per pass, batch one), about 6 hours more (SKIP_DECODE=1 skips it). Each
#    workload is its own result, never pooled;
# 6. the whole stacks with this card inside (tools/run_hil.py): the four realms, the four stacked with duplicates
#    (1,226) and the whole tower (656), each as 1, 10, 100 and 1,000 copies on one clock with the card inside, native
#    and Omni (repetitions 3, 3, 2, 1 by size; HIL_SCALES and HIL_REPS_BY_SCALE change them; SKIP_HIL=1 skips it);
#    the results so far are packed after every stage, so a stop loses nothing already measured;
# 7. packs every result folder into one file to send back, and prints the label each table chose by rule.
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
  $PY -c "import json,sys; h=json.load(open(sys.argv[1])).get('headline',{}); print('RESULT, BY RULE (compute-bound):', h.get('verdict','(no verdict)'))" \
    "results/gpu/run-$STAMP/GPU_REPS.json" 2>/dev/null || echo "no table produced (exit $confirm_rc)"
  if [ -z "${SKIP_DECODE:-}" ]; then
    echo "== second confirmation: AI token generation (preregistered: 10 repetitions, 600 s per arm, frozen code)"
    set +e
    PHASE=confirm WORKLOAD_ARGS="--kind decode" OUT="results/gpu/run-$STAMP-decode" bash scripts/gpu_paired.sh
    decode_rc=$?
    set -e
    PACK+=("results/gpu/run-$STAMP-decode")
    $PY -c "import json,sys; h=json.load(open(sys.argv[1])).get('headline',{}); print('RESULT, BY RULE (AI token generation):', h.get('verdict','(no verdict)'))" \
      "results/gpu/run-$STAMP-decode/GPU_REPS.json" 2>/dev/null || echo "no table produced (exit $decode_rc)"
  fi
  tar czf "results/gpu/omni-gpu-$STAMP-confirmations.tar.gz" "${PACK[@]}"
  echo "== both confirmations packed (send this now if you like; the stacks run next): results/gpu/omni-gpu-$STAMP-confirmations.tar.gz"
  if [ -z "${SKIP_HIL:-}" ]; then
    echo "== the whole stacks with this card inside: six organisms at 1x, 10x, 100x and 1,000x copies, native and Omni (tools/run_hil.py)"
    set +e
    ENV_FLOOR_W=$($PY -c "import json,sys; print(json.load(open(sys.argv[1]))['power_min_w'])" "$ENVELOPE") \
      NVIDIA_SMI="$SMI" GPU="$GPU" $PY tools/run_hil.py --out "results/hil/run-$STAMP" | tee "results/gpu/hil-$STAMP.log" | grep -E "^== |^\| |^- "
    hil_rc=${PIPESTATUS[0]}
    set -e
    PACK+=("results/hil/run-$STAMP")
    echo "whole stacks: exit $hil_rc (0 valid, 2 a validity problem, see results/hil/run-$STAMP/HIL.md)"
  fi
fi
tar czf "results/gpu/omni-gpu-$STAMP.tar.gz" "${PACK[@]}"
echo "== send this one file back: results/gpu/omni-gpu-$STAMP.tar.gz"
