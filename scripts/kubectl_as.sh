#!/usr/bin/env bash
# kubectl as the read-only shadow identity (deploy/pilot/rbac-shadow.yaml)
exec kubectl --as=system:serviceaccount:omni-shadow:omni-shadow "$@"
