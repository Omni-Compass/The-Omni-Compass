# Live repetitions, set 2: GitHub Actions run 36287072223 (commit 344617a, closure law in the live controller), 5 × native / omni / strict on kind

**Status: failed-request and latency rows are INVALID for the Omni arms (probe defect, see LIVE_REPS_PROBE_DEFECT.md).**
Node, node-hour and utilisation rows are valid. Kept here unedited as the record.

## B: Omni-Compass on top vs native, 5 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 2.619 | -56.3% | -3.837 to -2.924 | yes, better |
| node-hours | 1.517 | 0.6594 | -56.5% | -0.9753 to -0.7391 | yes, better |
| energy (Wh) | 167.4 | 165.3 | -1.3% | -4.924 to +0.7178 | no |
| response time (ms), mean | 206.8 | 222.9 | +7.8% | -90.32 to +122.6 | no |
| response time (ms), 95th percentile | 389.9 | 444.1 | +13.9% | -140.1 to +248.6 | no |
| response time (ms), 99th percentile | 511 | 571.6 | +11.9% | -222.3 to +343.5 | no |
| failed requests (%) | 0 | 49.79 | +0.0% | -6.999 to +106.6 | no |
| pending pods, pod-minutes | 0.42 | 0.1733 | -58.7% | -0.8374 to +0.3441 | no |
| utilisation (used / allocatable) | 0.07363 | 0.1505 | +104.4% | +0.05124 to +0.1024 | yes, better |

## C: Omni-Compass decides (strict) vs native, 5 paired repetitions

| Gauge | Native | Omni | Change | 95% interval of the difference | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 2.995 | -50.1% | -4.408 to -1.601 | yes, better |
| node-hours | 1.517 | 0.7554 | -50.2% | -1.123 to -0.3999 | yes, better |
| energy (Wh) | 167.4 | 165.4 | -1.2% | -4.118 to +0.1095 | no |
| response time (ms), mean | 206.8 | 228.5 | +10.5% | -65.28 to +108.7 | no |
| response time (ms), 95th percentile | 389.9 | 452.5 | +16.1% | -61.78 to +187.1 | no |
| response time (ms), 99th percentile | 511 | 630.9 | +23.5% | -86.79 to +326.6 | no |
| failed requests (%) | 0 | 16.28 | +0.0% | -28.91 to +61.47 | no |
| pending pods, pod-minutes | 0.42 | 0.5133 | +22.2% | -0.1259 to +0.3126 | no |
| utilisation (used / allocatable) | 0.07363 | 0.1374 | +86.7% | +0.02262 to +0.105 | yes, better |
