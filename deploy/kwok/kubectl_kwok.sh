#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# kubectl for the KWOK scale test (scripts/kwok_scale.sh). Everything goes to the real kubectl and the real API server,
# except `kubectl top nodes`: KWOK nodes are not machines and have no CPU use to report, so each Ready node is reported
# at 40% of its allocatable CPU (a steady, declared stand-in; the test measures the controller at scale, not a workload).
if [ "${1:-}" = "top" ] && [ "${2:-}" = "nodes" ]; then
  kubectl get nodes -o json | jq -r '.items[] | select(any(.status.conditions[]?; .type=="Ready" and .status=="True"))
    | "\(.metadata.name) \((.status.allocatable.cpu | tonumber? // 4) * 400)m 40% 1024Mi 6%"'
  exit 0
fi
exec kubectl "$@"
