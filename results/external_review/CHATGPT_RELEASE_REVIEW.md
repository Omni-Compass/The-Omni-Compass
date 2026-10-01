# Review of OmniCompass_SUPERVISORY_NERVOUS_SYSTEM_PROOF_RELEASE.zip (ChatGPT build), 27 September 2026

## What it is
The zip holds 442 files. Most are an older copy of this repository. It predates:
- the closure-law work (its `omnicompass/closure.py` lacks 144 lines of ours);
- the shield bug fixes (its `omnicompass/shield.py` still has both bugs the 2,000,000-case property test found);
- the pods-first coordination;
- the live probe fix.

Merging it wholesale would move the engine backwards.

**What it adds**
- A "recovery reflex" in `omnicompass/adapter.py` (10 lines) and an optional closed-loop equation-(2) mode.
- Its own `omnicompass/nervous_system.py`, with hand-set weights (for example `0.35 + 0.45 q + 0.25 E`).
- `hardware/cpufreq.py`: a Linux CPUFreq policy connector with snapshot and exact restore.
- `omnicompass/dcgm.py`: NVIDIA DCGM field numbers and a stub. It has no live path.
- A "grandmaster-safe" kind workflow, docs and a verifier.

Its own verifier and its three new tests pass when run here.

## Its headline claim, tested head to head
**The claim.** Its proof table compares its Omni with Kubernetes. It does not compare its Omni with this repository's
Omni, and that is the comparison that decides whether the change helps.

**The test.** Both engines ran on the same 100 held-out scenarios (stack benchmark, seed 360555127), paired per
scenario, with a 95% bootstrap interval. The full table is in `CHATGPT_REFLEX_HEAD_TO_HEAD.txt`.

**Throughput mode, its selected default.** This repository's engine is better on 11 gauges:
- healthy time
- physical violations
- power violations
- heat violations
- recovery time
- energy
- peak power
- node-hours
- reversals
- starts and stops
- round trips

The ChatGPT engine is better on one: average queue.

**Protect and direct modes.**

| Gauge | ChatGPT engine vs ours |
|---|---|
| Backlog | 53-55% lower |
| Queue | 41-44% lower |
| Power violations | 3-7 times higher |
| Heat violations | about 40 times higher |
| Energy | 4% higher |
| Peak power | 25% higher |

**Why.** The reflex does two things this repository's law does not:
- it adds machines when power is already at the ceiling;
- it lifts the power cap to 100% under backlog.

That overrides the power envelope. The rest of the reflex (never remove capacity while backlogged; add capacity up to
the requirement) is already in this repository's law (`delta < 0 and q >= guard_queue -> 0`).

**Verdict.** The reflex is a trade, not an improvement. The honest form of the same trade already exists here:
throughput mode, which beat it.

**Not adopted:**
- the reflex;
- the closed-loop mode (its own data shows worse health and more reversals);
- its nervous-system weights (hand-set; ours are derived from the engine: the equation-(2) release gate, basin
  health, the equation-6 stress equilibrium and unmet need);
- its shield (it still has the bugs).

## Adopted
**`hardware/cpufreq.py` (their connector), wired here under the nervous system**
(`omni_controller/muscles.py: _cpufreq_sysfs`, flags `--cpufreq-policy-root`, `--cpufreq-require-schedutil`).
- The ceiling is `min(max(cap, envelope floor, min(1, 1.25 u)), envelope ceiling)`.
- It never goes below the frequency schedutil itself would request at the current utilisation u. The lever therefore
  removes only headroom the scheduler is not using, and costs no performance by construction.
- The heat ceiling of the envelope wins last.
- The kill switch restores the operator's exact original ceilings. The earlier command-template lever restored the
  silicon maximum instead, which could raise a ceiling the operator had set lower. That gap is now closed.

**Tests.** `tests/test_cpufreq_contract.py` (in `verify.py`) runs about 1,900 random cases of utilisation, cap and
envelope. It checks:
- the schedutil floor;
- the envelope;
- the ceiling never rises above the operator's;
- exact restore;
- the governor gate.

**`tools/cpufreq_receipt.py`** is a read-only record of a machine's CPUFreq policies, taken before a hardware run.

**Still unproven.** Real silicon. A ceiling write is not a measurement of the delivered frequency, and GitHub-hosted
runners expose no CPUFreq policies.
