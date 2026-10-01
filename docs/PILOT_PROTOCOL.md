# Pilot Protocol

## Phase 0: Simulation evaluation (evaluator's own environment)
Run `python verify.py`. Pass criterion: VERIFICATION: PASS.

## Phase 1: Shadow (2 to 4 weeks)
- Capture: `OUT=capture.csv INTERVAL=15 DURATION=<seconds> POWER_CMD="<site power in watts>" bash fleet/capture/kube_capture.sh` (read-only).
- Replay: `python fleet/capture_replay.py capture.csv --idle-w <W> --dyn-w <W> --site-limit-w <W> --out replay/` gives Omni-Compass's recommended node count, power cap and HPA target per decision.
- Governor in OBSERVE on production telemetry read directly from nodes (kubelet/cAdvisor metrics, power meters, queue depth).
- No write credentials are issued.
- Logged per interval: directive, native actions taken, and the observed outcome.
- Pass criteria, agreed before start: logged directives never violate I1 to I5; counterfactual analysis on at least N recorded incidents shows the directive would have reduced time-to-recovery or energy without a backlog increase beyond an agreed bound.

## Phase 2: Guarded control, one loop at a time (4 to 8 weeks)
Order: power capping; node count (Cluster Autoscaler set to observe); replica count (HPA set to observe).
- Each loop is handed over separately, with the kill switch tested at handover and at exit.
- Pass criteria per loop, fixed in advance: SLO attainment not worse than the preceding shadow baseline at the agreed confidence level; zero shield invariant violations; energy per unit of completed work reported with confidence intervals.
- Exit: any criterion failed triggers the kill switch and returns the loop to its native controller.

## Scoring your own pilot
Capture the baseline (a period before the controller, or a matched node pool left on your normal autoscaler) and the
Omni-Compass period or pool with fleet/capture/kube_capture.sh, then:
`python pilot/score.py --baseline baseline.csv --omni omni.csv [--idle-w W --dyn-w W]`
It reports node-hours and energy per used CPU core-hour, utilisation, pending-pod minutes and HPA shortfall minutes, each
with a bootstrap 95% interval over hourly blocks. Energy is measured if the captures include power_w. Run long enough
for at least 24 blocks per side, and compare matched pools at the same time where possible, because traffic changes
between periods.

## Phase 3: Component retirement
A decision component is retired only after its loop has passed Phase 2 and a one-at-a-time removal shows no degradation (keep-or-remove rule, Manual Chapter 6). Execution and security components are retained.

## Reporting
All pilot metrics, including failures, are reported in the same format as the benchmark results.
