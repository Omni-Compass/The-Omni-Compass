#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# The 8-GPU result, one command on a rented machine with several NVIDIA cards (docs/GPU_RUN_GUIDE.md, section D):
#
#   sudo bash scripts/gpu_8card.sh
#
# Every card on the machine runs the whole card test at the same time (scripts/gpu_rented_run.sh with GPU=<card>): its
# own wire check, envelope, smoke, the two preregistered confirmations (compute and AI token generation) and the
# operator's power cap underneath, each card its own firmware alone against the firmware with Omni-Compass on top, on
# the same committed code. The cards share one machine, its power supply, its cooling and its neighbours' heat, as in a
# real server. Each card starts its arm rotation one step later than the card before it, so at any moment some cards
# run native and some run Omni-Compass, and no arm always meets the same neighbours.
# Then, with every card idle again: the GPU fault drill once, on card 0 (the master switch stops every governor on the
# machine, so it never runs while the cards measure). Then one pooled table per workload: every repetition of every
# card, paired within its own card (tools/gpu_reps.py), and each card's own table beside it.
#
# Last, the whole server as one: a language model served across every card at once (scripts/gpu_vllm.sh with GPU=all
# cards: vLLM tensor parallel, one Omni-Compass governor per card, the server's total GPU energy), SKIP_LLM=1 skips it.
# CARDS (default: every card nvidia-smi lists), SKIP_DECODE=1, SKIP_CAP=1, SKIP_DRILL=1 as in gpu_rented_run.sh. The
# whole stacks (HIL) run on the one-card machine and are skipped here.
set -uo pipefail
cd "$(dirname "$0")/.."
SMI="${NVIDIA_SMI:-nvidia-smi}"; PY="${PYTHON:-python3}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
[ "$(id -u)" = 0 ] || [ -n "${SIM:-}" ] || { echo "run with sudo: setting the power limit needs root"; exit 1; }
command -v "$SMI" >/dev/null || { echo "nvidia-smi not found: this machine has no NVIDIA driver"; exit 1; }
CARDS="${CARDS:-$($SMI --query-gpu=index --format=csv,noheader | tr -d ' ' | paste -sd, -)}"
IFS=, read -r -a C <<< "$CARDS"
echo "== $(( ${#C[@]} )) cards: ${CARDS}"
$SMI --query-gpu=index,name,power.limit,power.default_limit --format=csv,noheader
mkdir -p results/gpu
OUT="results/gpu/8card-$STAMP"; mkdir -p "$OUT"
echo "$CARDS" > "$OUT/cards.txt"

pids=()
for i in "${!C[@]}"; do
  g="${C[$i]}"
  echo "== card $g: starting (log $OUT/card-$g.log)"
  GPU="$g" CARD_TAG="card$g" STAMP="$STAMP" SKIP_DRILL=1 SKIP_HIL=1 SKIP_LLM=1 ROT_OFFSET="$i" \
    bash scripts/gpu_rented_run.sh > "$OUT/card-$g.log" 2>&1 &
  pids+=($!)
  sleep 5
done
echo "== all cards running. Progress: tail -f $OUT/card-*.log   (each card prints its own '== rep N, arm X' lines)"
rc=0
for i in "${!pids[@]}"; do
  wait "${pids[$i]}" || { echo "card ${C[$i]} exited $? (see $OUT/card-${C[$i]}.log)"; rc=1; }
done
echo "== every card finished"

if [ -z "${SKIP_DRILL:-}" ]; then
  echo "== the GPU fault drill on card ${C[0]}, every other card idle"
  GPU="${C[0]}" OUT="results/gpu/drill-$STAMP-8card" bash scripts/gpu_fault_drill.sh || rc=1
fi

if [ -z "${SKIP_LLM:-}" ]; then
  echo "== one model served across all ${#C[@]} cards (vLLM tensor parallel), one Omni-Compass governor per card"
  ENVELOPE="results/gpu/envelope-$STAMP-card${C[0]}.json" GPU="$CARDS" OUT="results/gpu/run-$STAMP-8card-llm" \
    bash scripts/gpu_vllm.sh || rc=1
fi

echo "== pooled tables: every card's repetitions, each paired within its own card"
for kind in "" -decode -cap -cap-full; do
  P="$OUT/pooled${kind:-}"; n=0
  for g in "${C[@]}"; do
    R="results/gpu/run-$STAMP-card$g$kind"
    [ -d "$R" ] || continue
    for r in "$R"/rep-*; do
      [ -d "$r" ] || continue
      mkdir -p "$P"; cp -r "$r" "$P/rep-$(( (g + 1) * 100 + ${r##*/rep-} ))"; n=$((n + 1))   # card 3, rep 7 -> rep-407
    done
  done
  [ "$n" -gt 0 ] || continue
  echo "-- ${kind#-}${kind:+ }(${kind:-compute}) $n repetitions"
  $PY tools/gpu_reps.py "$P" > "$P/table.log" 2>&1 || true
  $PY -c "import json,sys; h=json.load(open(sys.argv[1])).get('headline',{}); print('RESULT, BY RULE, ALL CARDS:', h.get('verdict','(no verdict)'))" \
    "$P/GPU_REPS.json" 2>/dev/null || echo "no pooled table (see $P/table.log)"
done

PACK=("$OUT")
for d in results/gpu/*-"$STAMP"-card* results/gpu/drill-"$STAMP"-8card results/gpu/run-"$STAMP"-8card-llm; do [ -e "$d" ] && PACK+=("$d"); done
tar czf "results/gpu/omni-8card-$STAMP.tar.gz" "${PACK[@]}"
echo "== send this one file back: results/gpu/omni-8card-$STAMP.tar.gz"
exit $rc
