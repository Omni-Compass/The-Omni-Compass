`hpa_independent.py` is an independent HPA implementation written separately from this package's harness and supplied
with an external k8s_controlplane harness. It is used unmodified; tests/test_hpa_three_way.py applies the upstream
scale-down window boundary (keep recommendations strictly newer than the cutoff) by subclassing.
