#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# The six organisms up the ladder of runs and sizes, on every core of this machine (tools/run_scale.py). Each rung
# writes results/scale/r<runs>-x<scale>/SCALE.md and is packed at the end. The grid tops out at 1,000 runs and 1,000x:
# by default 1,000 runs at 1x, 10x and 100x, and 100 runs at 1,000x (each receipt also shows the first 1, 10 and 100
# runs). Override: RUNGS="1000:1 1000:10".
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RUNGS="${RUNGS:-1000:1 1000:10 1000:100 100:1000}"
DIRS=()
for r in $RUNGS; do
  runs=${r%%:*}; scale=${r##*:}
  echo "== $runs runs, ${scale}x size, all six organisms, native and Omni"
  $PY tools/run_scale.py --runs "$runs" --scale "$scale" --out "results/scale/r$runs-x$scale" | tail -9
  DIRS+=("results/scale/r$runs-x$scale")
done
tar czf "results/scale/omni-scale-$STAMP.tar.gz" "${DIRS[@]}"
echo "== send this one file back: results/scale/omni-scale-$STAMP.tar.gz"
