# Capture schema (what this file is)

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
