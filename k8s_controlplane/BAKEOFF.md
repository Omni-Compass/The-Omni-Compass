# Bake-off that was actually run

Covering public set: HPA v2, PID, deadband threshold.
Same 15 s metric. Same replica bounds 1–40.

`frac_over_target` is a property of the frozen metric stream. It does not score SLO.

## PlanetLab recorded (9 traces, mean metric 0.086)

| Controller | Replica-hours | Scale events | Energy proxy |
|---|---|---|---|
| HPA 0.70 | 24.12 | 0.44 | 2.885 |
| Omni observe | 24.12 | 0.44 | 2.885 |
| Omni target | 24.09 | 0.44 | 2.884 |
| PID | 24.01 | 0.33 | 2.880 |
| Deadband | 24.01 | 2.00 | 2.881 |

Everyone sits at one replica.

## Synthetic archetypes (7 shapes, open-loop)

| Controller | Replica-hours | Scale events | Energy proxy |
|---|---|---|---|
| HPA 0.70 | 234.7 | 28.9 | 11.31 |
| Omni observe | 234.7 | 28.9 | 11.31 |
| Omni target | 87.0 | 43.9 | 5.40 |
| PID | 172.2 | 195.1 | 8.81 |
| Deadband | 74.0 | 105.0 | 4.88 |

Omni observe = HPA. Omni target raises ρ* above 0.70, so HPA asks for fewer replicas. PID chatters. Deadband is cheapest on this open-loop cost metric.
