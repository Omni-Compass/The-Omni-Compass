#!/usr/bin/env bash
# Run kubectl as the Omni-Compass service account (deploy/kind/rbac-omni.yaml), never as cluster admin.
set -euo pipefail
exec kubectl --as=system:serviceaccount:omni-compass:omni-compass "$@"
