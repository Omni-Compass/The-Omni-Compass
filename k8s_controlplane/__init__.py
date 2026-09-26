"""Referee harness: metrics-server + HPA + Cluster Autoscaler / Karpenter-lite + Omni-Compass.

This is an algorithm replica of documented Kubernetes control-plane behaviour.
It is not kube-controller-manager, cluster-autoscaler, or Karpenter source.
"""
from .config import HarnessConfig
from .benchmark import ARMS, run, simulate
