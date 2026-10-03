#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# The GPU fault drill: what happens to the card when things go wrong with Omni-Compass on it. About 10 minutes, with
# the pinned request stream running the whole time. Every check must pass; the card must end at its own settings.
#   1 crash     the governor is killed outright (SIGKILL: no chance to hand back); the watchdog
#               (tools/omni_switch.py watchdog --once) must put the card's limit and clocks back
#   2 switch    the master switch is pulled while the governor runs; it must hand back and exit, and refuse to restart
#               until the switch is on again
#   3 blind     the response-time feed stops (the workload is paused); the governor must fail up (ceiling to the top,
#               the lid to the start) within its next decisions
# Usage: sudo OUT=results/gpu/drill-STAMP bash scripts/gpu_fault_drill.sh   (SIM=1 with tests/fake_gpu for a dry run)
set -uo pipefail
cd "$(dirname "$0")/.."
SMI="${NVIDIA_SMI:-nvidia-smi}"; PY="${PYTHON:-python3}"; GPU="${GPU:-0}"; OUT="${OUT:?set OUT}"
STEP="${DRILL_STEP_S:-60}"
mkdir -p "$OUT"; export OMNI_MASTER_OFF="${OMNI_MASTER_OFF:-/tmp/omni-compass/OFF}"
lim() { $SMI -i "$GPU" --query-gpu=power.limit --format=csv,noheader,nounits | tr -d ' ' | cut -d. -f1; }
START=$(lim); PASS=(); FAIL=()
check() { if eval "$2"; then PASS+=("$1"); echo "PASS  $1" | tee -a "$OUT/DRILL.md"; else FAIL+=("$1"); echo "FAIL  $1" | tee -a "$OUT/DRILL.md"; fi; }
echo "# GPU fault drill" > "$OUT/DRILL.md"; echo "" >> "$OUT/DRILL.md"
echo "Card start limit $START W; step $STEP s; commit $(git -c safe.directory='*' rev-parse --short HEAD 2>/dev/null)." >> "$OUT/DRILL.md"; echo "" >> "$OUT/DRILL.md"
$PY tools/gpu_workload.py calibrate --out "$OUT" --device "cuda:$GPU" ${SIM:+--sim} >/dev/null
SLO=$($PY -c "import json; print(round(10*json.load(open('$OUT/calib.json'))['service_ms'],1))")
$PY tools/gpu_workload.py run --calib-file "$OUT/calib.json" --out "$OUT/wl" --device "cuda:$GPU" --duration $(( STEP * 9 )) --drain 5 ${SIM:+--sim} > "$OUT/workload.log" 2>&1 &
WL=$!
gov() { $PY -m omni_controller.gpu_bowl --mode cap --gpus "$GPU" --smi "$SMI" --interval 2 --audit "$OUT/audit-$1.jsonl" \
          --kill-file "$OUT/kill-$1" --latency-file "$OUT/wl/latency.csv" --slo-ms "$SLO" --learn-samples 3 > "$OUT/governor-$1.log" 2>&1 & echo $!; }
sleep 10
# 1 crash
G=$(gov crash); sleep "$STEP"
kill -9 "$G" 2>/dev/null; sleep 2
$PY tools/omni_switch.py watchdog --once > "$OUT/watchdog.json" 2>&1
check "crash: the governor killed outright, the watchdog handed the card back (limit $(lim) W, start $START W)" '[ "$(lim)" = "$START" ] && grep -q "\"ok\": true" "$OUT/watchdog.json"'
# 2 master switch
G=$(gov switch); sleep "$STEP"
$PY tools/omni_switch.py off --reason "fault drill" --wait 60 > "$OUT/switch.txt" 2>&1
wait "$G" 2>/dev/null
check "switch: the master switch pulled, the governor handed back and exited (limit $(lim) W)" 'grep -q "every governor has restored and exited" "$OUT/switch.txt" && [ "$(lim)" = "$START" ]'
$PY -m omni_controller.gpu_bowl --mode cap --gpus "$GPU" --smi "$SMI" --interval 2 --audit "$OUT/audit-refused.jsonl" --duration 5 > "$OUT/refused.log" 2>&1
check "switch: while OFF, a governor refuses to start" 'grep -q "master switch is OFF" "$OUT/refused.log"'
$PY tools/omni_switch.py on > /dev/null
# 3 blind
G=$(gov blind); sleep "$STEP"
kill -STOP "$WL" 2>/dev/null; sleep 30
check "blind: the response-time feed stopped, the governor failed up (ceiling to the top, the lid to the start)" \
  'tail -n 5 "$OUT/audit-blind.jsonl" | grep -q "blind_fail_up"'
kill -CONT "$WL" 2>/dev/null
touch "$OUT/kill-blind"; sleep 6; kill "$G" 2>/dev/null; wait "$G" 2>/dev/null
kill "$WL" 2>/dev/null; wait "$WL" 2>/dev/null
$SMI -i "$GPU" -rgc >/dev/null 2>&1; [ "$(lim)" = "$START" ] || $SMI -i "$GPU" -pl "$START" >/dev/null 2>&1
check "end: the card at its own start limit ($(lim) W)" '[ "$(lim)" = "$START" ]'
{ echo ""; echo "Passed ${#PASS[@]} of $(( ${#PASS[@]} + ${#FAIL[@]} ))."; } | tee -a "$OUT/DRILL.md"
[ "${#FAIL[@]}" = 0 ]
