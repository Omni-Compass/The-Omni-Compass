# Live repetitions, set 7: GitHub Actions run 36306110975 (attempt 3), repository Omni-Compass/the-omni-compass, commit f6f76be

This is the first live set with the two-way nervous system and the machine-organ release gate. Real Kubernetes
(kind, 7 nodes: 1 control plane and 6 workers) on GitHub runners, with 5 paired repetitions per arm.

## B: Omni-Compass on top vs native
| Gauge | Native | Omni | Change | 95% interval | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 6 | +0.0% | ~0 | no |
| node-hours | 1.512 | 1.515 | +0.2% | -0.009 to +0.015 | no |
| energy (Wh) | 167 | 167.1 | +0.0% | -2.15 to +2.31 | no |
| response time (ms), mean | 206.9 | 247.6 | +19.7% | -41.8 to +123.2 | no |
| response time (ms), p95 | 417.1 | 502.7 | +20.5% | -54.6 to +225.7 | no |
| response time (ms), p99 | 549.4 | 709.8 | +29.2% | -43.3 to +364.1 | no |
| failed requests (%) | 0 | 0 | 0 | 0 | no |
| pending pods, pod-minutes | 0.4 | 0.403 | +0.8% | -0.36 to +0.36 | no |
| utilisation | 0.0744 | 0.0732 | -1.6% | -0.007 to +0.004 | no |

## C: Omni-Compass decides (strict) vs native
| Gauge | Native | Omni | Change | 95% interval | Significant |
|---|---:|---:|---:|---:|---|
| worker nodes in service, mean | 6 | 6 | +0.0% | ~0 | (identical) |
| node-hours | 1.512 | 1.511 | -0.1% | -0.016 to +0.012 | no |
| energy (Wh) | 167 | 165.9 | -0.7% | -4.14 to +1.86 | no |
| response time (ms), mean | 206.9 | 216.7 | +4.7% | -102 to +122 | no |
| response time (ms), p95 | 417.1 | 444.6 | +6.6% | -147 to +202 | no |
| response time (ms), p99 | 549.4 | 617.5 | +12.4% | -133 to +270 | no |
| failed requests (%) | 0 | 0 | 0 | 0 | no |
| pending pods, pod-minutes | 0.4 | 0.417 | +4.2% | -0.36 to +0.39 | no |
| utilisation | 0.0744 | 0.0699 | -6.0% | -0.013 to +0.004 | no |

## Reading
**Result.** Equal to native on every gauge. No difference is significant, and there were 0 failed requests in every
arm. Omni-Compass kept all 6 machines again.

**The two-way wiring worked live.**
- No sense was ever blind: latency age stayed at 7 s or less.
- Every command landed: HPA drift was 0.0 each time it was checked.
- Each breach at a load step was recorded as "latency breached now".

**Why no machine was released.** The machine organ's own calm peaked at 0.65, and it needs 0.7. The offline replay
reproduces this exactly:
- the run's heat model settles at 0.34 + 0.62 x power stress, about 0.62, from mostly idle power;
- at that heat U settles at 0.946 and calm at 0.637.

**The flaw.** Power and heat are relieved by a release, never worsened by it, yet they vetoed every release.

**Fix (next commit).** The machine organ's view no longer counts power stress or heat against a release. Security,
blind senses, live breaches, pods scaling up and the headroom proof still apply. It is judged by live set 8.
