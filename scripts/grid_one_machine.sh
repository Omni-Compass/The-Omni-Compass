#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# The six organisms on one rented machine, one command (docs/REALMS_PREREGISTRATION.md, the 1,000-copy size): the
# grid cells too large for GitHub's runners, by default 100 runs of every organism at 1,000 copies (seeds 7000 on, the
# same seeds as every other cell, so the 1-run and 10-run blocks nest inside it).
#
#   nohup bash scripts/grid_one_machine.sh > grid.log 2>&1 &
#
# Each organism runs in turn with as many processes as the machine's cores and memory allow (memory per process by
# organism at 1,000 copies, measured: tools/run_scale.py after the packing of realms/plants.py). Every finished
# organism is saved at once (parts/<organism>/SCALE.json), so a run that stops part way keeps what it finished, and a
# restart skips the organisms already done. At the end: one receipt, SIX-<size>x.md, the file to send back.
# SCALE (default 1000), RUNS (default 100), ORGS (default "5 6 1 3 4 2", largest first), MEM_FRACTION (default 0.85).
set -uo pipefail
cd "$(dirname "$0")/.."
SCALE="${SCALE:-1000}"; RUNS="${RUNS:-100}"; ORGS="${ORGS:-5 6 1 3 4 2}"; FRAC="${MEM_FRACTION:-0.85}"
OUT="results/scale/one-machine-${SCALE}x"; mkdir -p "$OUT/parts"
CORES=$(nproc); MEM_GB=$(awk '/MemTotal/ {print int($2/1048576)}' /proc/meminfo)
# GB per process at 1,000 copies (the four stacked 9, the tower 5, the realms 2.5 to 3), scaled to the size asked
declare -A GB=([1]=3 [2]=2.5 [3]=2.5 [4]=3 [5]=9.5 [6]=5)
echo "== $CORES cores, $MEM_GB GB memory; ${RUNS} runs of organisms ${ORGS} at ${SCALE} copies; commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
pip install -q -r requirements.txt >/dev/null 2>&1 || true
for o in $ORGS; do
  if [ -f "$OUT/parts/$o/SCALE.json" ]; then echo "== organism $o already done, skipped"; continue; fi
  w=$(python3 -c "import math; g=${GB[$o]}*$SCALE/1000; print(max(1, min($CORES, $RUNS, int($MEM_GB*$FRAC/max(g,0.2)))))")
  echo "== organism $o: $w processes, started $(date -u +%H:%M) UTC"
  python3 tools/run_scale.py --runs "$RUNS" --first 0 --scale "$SCALE" --organisms "$o" --out "$OUT/parts/$o.tmp" --workers "$w" \
    || { echo "organism $o stopped (see above); the organisms finished so far are kept"; exit 1; }
  rm -rf "$OUT/parts/$o"; mv "$OUT/parts/$o.tmp" "$OUT/parts/$o"
  echo "== organism $o done $(date -u +%H:%M) UTC"
done
python3 tools/pool_scale.py "$OUT/SIX-${SCALE}x.md" "$OUT/parts/*/SCALE.json"
cp "$OUT/SIX-${SCALE}x.md" "SIX-${SCALE}x.md"
echo "== send this one file back: SIX-${SCALE}x.md (also in $OUT)"
