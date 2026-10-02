#!/usr/bin/env bash
# The six organisms up the ladder of runs and sizes, on every core of this machine (tools/run_scale.py). Each rung
# writes results/scale/r<runs>-x<scale>/SCALE.md and is packed at the end. Rungs by default: 100 and 1,000 runs at 1x,
# 100 runs at 10x. Override: RUNGS="100:1 1000:1 100:10 1000:10".
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RUNGS="${RUNGS:-100:1 1000:1 100:10}"
DIRS=()
for r in $RUNGS; do
  runs=${r%%:*}; scale=${r##*:}
  echo "== $runs runs, ${scale}x size, all six organisms, native and Omni"
  $PY tools/run_scale.py --runs "$runs" --scale "$scale" --out "results/scale/r$runs-x$scale" | tail -9
  DIRS+=("results/scale/r$runs-x$scale")
done
tar czf "results/scale/omni-scale-$STAMP.tar.gz" "${DIRS[@]}"
echo "== send this one file back: results/scale/omni-scale-$STAMP.tar.gz"
