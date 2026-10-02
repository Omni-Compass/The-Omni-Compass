# schedutil and the Omni-Compass CPU ceiling

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

## The kernel law (CFS, frequency-invariant)

```
f_des = min(f_max, 1.25 u f_max)
```

The 1.25 is not a guess. It puts the tip at 80% utilisation, so the CPU asks for f_max before it is pinned. The driver
then snaps to the next available frequency (OPP) and clips to the policy. In the kernel
(`kernel/sched/cpufreq_schedutil.c`, `get_next_freq`) this is `freq = (freq + (freq >> 2)) * util / max`, followed by
`cpufreq_driver_resolve_freq`. The `>> 2` is the 1.25.

## Limits that actually stop it

| Limit | Role |
|---|---|
| cpuinfo_min_freq / cpuinfo_max_freq | the silicon's OPPs |
| scaling_min_freq / scaling_max_freq | the policy cap: **this is the Omni-Compass ceiling** |
| thermal / PM QoS | can pull the maximum down |
| uclamp | clamps the utilisation schedutil sees |
| RT / deadline | ignore the 1.25 map and go to the policy maximum |
| rate_limit_us | drops requests inside the window |
| iowait boost | inflates u after an IO wakeup |

## This repository

| Where | What it is | Faithful to the kernel? |
|---|---|---|
| `hardware/plant.py`, arm A | `native = min(1.0, max(f_min, 1.25 * want))` | the same map; `want` is fleet demand, not PELT; no OPP grid, no RT jump, no rate limit |
| `hardware/plant.py`, arm B | `min(native, cap)` | the right shape for writing scaling_max_freq; it is **not** a second schedutil |
| `hardware/schedutil.py` | `get_next_freq` (>> 2), OPP resolve (lowest OPP >= request), policy/thermal clamp, uclamp, RT to policy max, rate limit (a lowered ceiling still applies at once), iowait boost | kernel-shaped model; tested in `tests/test_schedutil.py` |
| `scripts/cpufreq_ceiling.sh` | writes scaling_max_freq on every policy (clamped to cpuinfo limits); `restore` puts cpuinfo_max_freq back | the real write; tested against a fake sysfs in `tests/test_cpufreq_ceiling.py` |
| `omni_controller/muscles.py`, cpu_pstate | the live muscle: `--cpufreq-cmd "bash scripts/cpufreq_ceiling.sh {khz}"`, ceiling = cpu_max_khz x power cap; the kill switch writes the maximum back | needs root on a real machine; kind nodes have no cpufreq |

## What is not claimed

- **intel_pstate / HWP** is a different governor: the hardware chooses the frequency within the limits. Writing
  scaling_max_freq still bounds it, but this plant does not model HWP, and results here are not HWP results.
- The plant's CPU saving is small (about 3.5% in the device study) because schedutil already follows demand. The ceiling
  mainly buys heat and power headroom, not energy per unit of work.
