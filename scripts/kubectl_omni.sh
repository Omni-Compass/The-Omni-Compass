#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# Run kubectl as the Omni-Compass service account (deploy/kind/rbac-omni.yaml), never as cluster admin.
set -euo pipefail
exec kubectl --as=system:serviceaccount:omni-compass:omni-compass "$@"
