# Probe defect in live repetition sets 1 and 2 (found 27 September 2026)

**What was seen**
- Omni arms showed 16-66% failed requests.
- Native showed 0%.
- Response times were 8-26% higher.

**Cause**
- The response-time probe reached php-apache through `kubectl port-forward svc/php-apache`. That tunnel attaches to
  one pod, not to the Service.
- When Omni drained the worker holding that pod, the tunnel hung instead of exiting. The restart loop never fired:
  the job log reads `port_forward.log: No such file or directory`.
- Every later request timed out and counted as failed.
- Native never drains, so only the Omni arms were exposed. The failures are a measurement fault, not user-visible
  outages.

**How the fix follows from the defect** (`deploy/kind/bench-serving.yaml`, `scripts/kind_bench.sh`)
- The probe now enters through a NodePort Service on the control-plane node, which is never parked.
- kube-proxy load-balances each request across the ready endpoints, as for a real client. A request that fails
  because a drain moved a pod is still counted.
- A PodDisruptionBudget (`minAvailable: 1`, the standard Kubernetes guard) stops a drain from evicting the last ready
  replica. A blocked drain gives up after 45 s and the node stays in service.
- Both arms get the same Service and budget.

**What stays valid from sets 1 and 2**
- Nodes in service.
- Node-hours.
- Utilisation.
- Energy (modelled; parked workers are counted at standby power).

**What is replaced**
- Failed requests and response times: replaced by set 3 (the first `[reps]` run after this fix).
