# Live repetitions, set 1: GitHub Actions run 36286889273 (commit eae9efc), 5 × native / omni / strict on kind

**Status: failed-request and latency rows are INVALID for the Omni arms (probe defect, see LIVE_REPS_PROBE_DEFECT.md).**
Node rows are valid. Kept here unedited as the record.

## B: Omni-Compass on top vs native, 5 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 5.145 | -14.3% | -2.209 to +0.4985 | no |
| node-hours | 1.516 | 1.3 | -14.2% | -0.5569 to +0.1263 | no |
| energy (Wh) | 166.9 | 166.6 | -0.2% | -1.941 to +1.248 | no |
| response time (ms), mean | 208 | 262.4 | +26.2% | -46.67 to +155.5 | no |
| response time (ms), 95th percentile | 387.2 | 487.5 | +25.9% | -40.58 to +241 | no |
| response time (ms), 99th percentile | 501.1 | 581.2 | +16.0% | -133.7 to +293.9 | no |
| failed requests (%) | 0 | 66.49 | +0.0% | +18.09 to +114.9 | yes, worse |
| pending pods, pod-minutes | 0.3333 | 0.5933 | +78.0% | -0.5461 to +1.066 | no |
| utilisation (used / allocatable) | 0.07224 | 0.08547 | +18.3% | -0.0137 to +0.04015 | no |

## C: Omni-Compass decides (strict) vs native, 5 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 4.582 | -23.6% | -2.921 to +0.08574 | no |
| node-hours | 1.516 | 1.159 | -23.5% | -0.7421 to +0.02866 | no |
| energy (Wh) | 166.9 | 166.3 | -0.4% | -3.385 to +2.065 | no |
| response time (ms), mean | 208 | 246.9 | +18.7% | -42.59 to +120.4 | no |
| response time (ms), 95th percentile | 387.2 | 469.8 | +21.3% | -27.85 to +193.1 | no |
| response time (ms), 99th percentile | 501.1 | 599.2 | +19.6% | -20.64 to +216.9 | no |
| failed requests (%) | 0 | 41.68 | +0.0% | -12.96 to +96.31 | no |
| pending pods, pod-minutes | 0.3333 | 0.4733 | +42.0% | -0.109 to +0.389 | no |
| utilisation (used / allocatable) | 0.07224 | 0.09439 | +30.7% | -0.004397 to +0.04869 | no |
