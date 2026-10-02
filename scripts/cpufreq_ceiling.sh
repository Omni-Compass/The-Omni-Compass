#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# Omni-Compass CPU frequency ceiling on a real Linux machine: writes scaling_max_freq for every cpufreq policy.
#   cpufreq_ceiling.sh KHZ       set the ceiling (clamped to each policy's [cpuinfo_min_freq, cpuinfo_max_freq])
#   cpufreq_ceiling.sh restore   kill switch: scaling_max_freq back to cpuinfo_max_freq
# schedutil keeps choosing frequencies inside the ceiling (hardware/SCHEDUTIL.md). Needs root. SYSFS overrides the
# root (tests). Used by the live controller as: --cpufreq-cmd "bash scripts/cpufreq_ceiling.sh {khz}"
set -euo pipefail
SYSFS="${SYSFS:-/sys/devices/system/cpu/cpufreq}"
arg="${1:?usage: cpufreq_ceiling.sh KHZ|restore}"
n=0
for pol in "$SYSFS"/policy*; do
  [ -d "$pol" ] || continue
  lo=$(cat "$pol/cpuinfo_min_freq"); hi=$(cat "$pol/cpuinfo_max_freq")
  if [ "$arg" = "restore" ]; then
    want=$hi
  else
    want=$(printf '%.0f' "$arg"); (( want < lo )) && want=$lo; (( want > hi )) && want=$hi
  fi
  echo "$want" > "$pol/scaling_max_freq"; n=$((n + 1))
  echo "$(basename "$pol") scaling_max_freq=$want (cpuinfo $lo-$hi, governor $(cat "$pol/scaling_governor" 2>/dev/null || echo ?))"
done
(( n > 0 )) || { echo "no cpufreq policies under $SYSFS" >&2; exit 1; }
