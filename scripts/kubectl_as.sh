#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
# kubectl as the read-only shadow identity (deploy/pilot/rbac-shadow.yaml)
exec kubectl --as=system:serviceaccount:omni-shadow:omni-shadow "$@"
