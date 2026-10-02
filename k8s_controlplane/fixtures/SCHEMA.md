# Capture schema (what this file is)

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../../LICENSE).

`METRICS_SERVER_CAPTURE.csv` is PlanetLab CPU percent, hold-last to 15 s,
plus an HPA v2 algorithm column. Column names follow the metrics-server / HPA
status shape. The values are not from a cluster.

| column | this file |
|---|---|
| cpu_utilization | PlanetLab percent / 100 |
| cpu_millicores_avg | utilization × declared 200 m |
| request_millicores | declared 200 |
| ready_replicas / current_replicas | walked by the HPA algorithm after fill |
| cluster_desired_replicas | independent HPA v2 on that metric |
| target_utilization | 0.70 |
| source | `planetlab_util+hpa_v2_algorithm_status` |
