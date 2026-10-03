#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# Real AI serving on the card: a language model served by vLLM, the card's firmware alone against the firmware with
# Omni-Compass on top (scripts/gpu_paired.sh with tools/llm_workload.py as the workload). vLLM is installed in its own
# environment (it pins its own PyTorch), so nothing else on the machine changes. If it cannot be installed or started,
# the stage says so and exits without touching anything measured before it.
#
#   sudo OUT=results/gpu/run-STAMP-llm ENVELOPE=... bash scripts/gpu_vllm.sh
#   LLM_MODEL (default Qwen/Qwen2.5-0.5B-Instruct, open, no account needed), LLM_RATE (requests per second, default 4),
#   REPS_LLM (default 5), DURATION_LLM (default 300 s per arm)
# Several cards: GPU=0,1,2,3,4,5,6,7 serves one model across them (vLLM tensor parallel, one Omni-Compass governor per
# card); LLM_MODEL then defaults to Qwen/Qwen2.5-7B-Instruct (open, no account needed).
# Your own serving engine: start it yourself (vLLM, TensorRT-LLM's trtllm-serve, SGLang, NVIDIA NIM, Triton's
# OpenAI-compatible frontend: anything that answers /v1/completions), then LLM_URL=http://host:port LLM_MODEL=<name>
# runs the same paired test against it; nothing is installed or started.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT="${OUT:?set OUT}"; GPU="${GPU:-0}"
IFS=, read -r -a CARDS <<< "$GPU"; TP=${#CARDS[@]}
DEFMODEL=Qwen/Qwen2.5-0.5B-Instruct; [ "$TP" = 1 ] || DEFMODEL=Qwen/Qwen2.5-7B-Instruct
VENV="${VLLM_VENV:-/opt/omni-vllm}"; MODEL="${LLM_MODEL:-$DEFMODEL}"; PORT="${LLM_PORT:-8000}"
mkdir -p "$OUT"
if [ -n "${LLM_URL:-}" ]; then
  echo "== your own serving engine at $LLM_URL (model $MODEL): nothing installed or started"
  curl -sf "$LLM_URL/v1/models" >/dev/null 2>&1 || { echo "nothing answers at $LLM_URL/v1/models" | tee "$OUT/SKIPPED.txt"; exit 0; }
else
echo "== real AI serving: installing vLLM in its own environment ($VENV)"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" && "$VENV/bin/pip" install -q --upgrade pip && "$VENV/bin/pip" install -q vllm \
    || { echo "vLLM could not be installed on this machine; real AI serving skipped (nothing else is affected)" | tee "$OUT/SKIPPED.txt"; exit 0; }
fi
echo "== starting the model server: $MODEL"
CUDA_VISIBLE_DEVICES="$GPU" "$VENV/bin/python" -m vllm.entrypoints.openai.api_server --model "$MODEL" --port "$PORT" \
  --gpu-memory-utilization 0.80 --max-model-len 2048 --tensor-parallel-size "$TP" > "$OUT/vllm.log" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null; wait $SRV 2>/dev/null' EXIT
for _ in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && break
  kill -0 "$SRV" 2>/dev/null || break
  sleep 5
done
curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 \
  || { echo "the model server did not start; real AI serving skipped (see $OUT/vllm.log)" | tee "$OUT/SKIPPED.txt"; exit 0; }
LLM_URL="http://127.0.0.1:$PORT"
fi
export LLM_URL LLM_MODEL="$MODEL"
python3 tools/llm_workload.py calibrate --out "$OUT" > "$OUT/calibrate.log" 2>&1 \
  || { echo "calibration failed; real AI serving skipped" | tee "$OUT/SKIPPED.txt"; exit 0; }
SLO=$(python3 -c "import json; print(round(10*json.load(open('$OUT/calib.json'))['service_ms'],1))")
echo "one request at a time: $(python3 -c "import json; print(round(json.load(open('$OUT/calib.json'))['service_ms']))") ms; response line $SLO ms"
PHASE=confirm REPS_CONFIRM="${REPS_LLM:-5}" DURATION="${DURATION_LLM:-300}" SLO_MS="$SLO" GPU="$GPU" \
  WORKLOAD_CMD="python3 tools/llm_workload.py run" OUT="$OUT" bash scripts/gpu_paired.sh
