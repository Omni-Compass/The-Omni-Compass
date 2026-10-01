# GPU bench: native vs Omni-Compass, metered by the device

## Every column, mean over repetitions

| Gauge |  |
|---|
| work per wall energy (served requests per kJ, whole machine) |  |
| energy, whole machine at the wall (J) |  |
| energy, CPU package (J) |  |
| energy, DRAM (J) |  |
| energy, platform psys (J) |  |
| energy, rest of the machine (J) |  |
| energy, GPU device counter (J) |  |

## The control

- Power-limit writes executed: .
- Every arm ended at the start limit.
- Energy is the device's own power.draw integrated over time; no number here is modelled.
