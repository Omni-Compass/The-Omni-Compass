# Running the GPU test yourself, step by step

> **PROPRIETARY - EVALUATION AND SIMULATION USE ONLY.** Copyright (c) 2026 The Omni-Compass LLC. This is not open-source software (`SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0`). Any commercial use, commercialization, monetization, production use, redistribution, hosted service or incorporation into a product requires a signed, paid **Omni-Compass Enterprise License** from The Omni-Compass LLC. Protected by copyright, patents and trademarks: Patent applications, copyright registrations and trademark applications covering the Omni-Compass engine, its mathematics and its software have been filed in the United States by The Omni-Compass LLC. See [`LICENSE`](../LICENSE).

> **Before you wire anything:** read [`DISCLOSURES.md`](../DISCLOSURES.md). Omni-Compass acts only through the wires it is given; it cannot be slapped on. If your paired receipts differ from the published benchmarks in direction, the first presumption is wiring: confirm the installation with section 8.5 of the manual (*Wired right or wired wrong*).

There are three ways to get real-machine numbers:
- **Your own tower:** a machine you control, with a smart plug measuring the whole machine at the wall (section A).
- **GitHub's GPU machines:** they run the test from the repository with one click (section B).
- **A rented cloud GPU:** sections 1 to 6.

## A. Your own tower, measured at the wall

You need:
- an NVIDIA graphics card (a GeForce RTX works);
- Linux on that machine (a spare drive or a USB boot is fine);
- a smart plug that reports watts, for example a Shelly Plus Plug or any plug running Tasmota, which cost about
  $20 to $30.

Plug the tower into the smart plug, and connect the plug to your home Wi-Fi with its own app. Note its IP address,
shown in the app or on your router's device list. Then on the tower:

```bash
python3 tools/wall_meter.py shelly2:192.168.1.50 --once        # prints the tower's watts right now
sudo WALL_METER=shelly2:192.168.1.50 bash scripts/gpu_paired.sh                  # trial run
sudo WALL_METER=shelly2:192.168.1.50 PHASE=confirm bash scripts/gpu_paired.sh    # the real test
```

Use `shelly1:` for older Shelly plugs and `tasmota:` for Tasmota plugs. The table then adds whole-machine energy at
the wall and requests served per wall kilojoule. The plug is read by the test only; Omni never sees it, so its number
is independent of Omni.

## B. GitHub's own GPU machines

1. **One-time setup, by an owner of the Omni-Compass organisation on GitHub:**
   1. Go to **Settings → Actions → Runners → New runner → New GitHub-hosted runner**.
   2. Choose the image **NVIDIA GPU-Optimized Image for Linux** and a GPU size.
   3. Name its label `gpu-t4`, or set the repository variable `GPU_RUNNER` to the label you chose.

   GPU runners are billed per minute on paid plans.
2. **To run:** go to **Actions → gpu-bench → Run workflow**, then choose `smoke` or `confirm`.
3. **Results:** each repetition runs on its own GPU machine. The results are pooled into one table, shown on the run's
   summary page, and every raw file is committed back to the branch under `results/gpu/github-<run id>/`.

If GitHub's machines don't allow changing the GPU power limit, the job stops in its first minute and says so.

## C. A rented cloud GPU

This costs roughly $10 to $25 in rented GPU time. You type a
handful of commands; the machine does the rest.

## 1. Rent the right kind of machine

The test changes the GPU's power limit, so you need a machine where you are the full administrator of the GPU:

- **Use a virtual machine (VM) or a bare-metal server.** Lambda Cloud "on-demand instances" are VMs; so are the GPU
  instances on AWS, Google Cloud and Azure.
- **Avoid "container" or "pod" rentals.** Their GPUs usually block power-limit changes. This is common on the cheapest
  per-hour marketplaces.
- **Any single NVIDIA data-center GPU works:** A10, L4, A100, H100, L40S. One GPU is enough.
- **Choose an image that already has PyTorch.** On Lambda that is the default "Lambda Stack" image.

You don't have to guess whether a machine allows it. In its first minute the test checks, and stops with *"cannot set
the power limit (run as root)"* if the machine doesn't allow it. If you see that, shut the machine down (you pay only
for the minutes used) and rent a different kind.

## 2. Connect to it

The rental site shows a command like `ssh ubuntu@123.45.67.89`. Paste it into Terminal (Mac) or PowerShell (Windows).

## 3. Get the code

On the rented machine (the repository is public while the benchmarks run; if it is private, use a read-only
fine-grained token in the URL):

```bash
git clone https://github.com/The-Omni-Compass-LLC/The-Omni-Compass the-omni-compass
cd the-omni-compass
git log --oneline -1       # the commit you are about to test; write it down
pip install -r requirements.txt
nvidia-smi                 # should show your GPU
```

## 4. The whole test, one command (about 45 hours)

```bash
sudo nohup bash scripts/gpu_rented_run.sh > run.log 2>&1 &
tail -f run.log            # Ctrl+C stops watching; the test keeps running
```

It runs, in order, and stops at the first failure:
1. the machine check (one copy only, nothing else on the card, the card's default limit and clock range restored);
2. the **wire check**, which must end `WIRED RIGHT` (manual, section 8.4);
3. the smoke test, about 40 minutes, never counted;
4. the preregistered confirmation on compute-bound work: 10 repetitions × native / watch / Omni, 600 s each, about
   6 hours;
5. the second preregistered confirmation on AI token generation (memory-bound), the same design, about 6 hours
   (`SKIP_DECODE=1` skips it); each is its own result, never pooled. Both are packed into one file as soon as they
   finish: `results/gpu/omni-gpu-<stamp>-confirmations.tar.gz`;
6. **an operator's power cap underneath** (70% of the card's default limit): the cap alone vs the cap with
   Omni-Compass on top, at the usual load and fully loaded (more work from the same watts), about 3 hours
   (`SKIP_CAP=1` skips it);
7. **the GPU fault drill**, about 10 minutes: the governor killed outright, the master switch pulled, the response
   feed blind; every check must pass (`SKIP_DRILL=1` skips it). Everything so far is then packed into
   `results/gpu/omni-gpu-<stamp>-partial.tar.gz`;
8. the six organisms with this card inside, each as **1, 10, 100 and 1,000 copies** on one clock (3, 3, 2 and 1
   repetitions), about 25 hours; the 1,000-copy stacks need a longer step than 2 s, measured on the machine and stated
   in the receipt (`SKIP_HIL=1` skips this stage);
9. **real AI serving** last: a small open language model served by vLLM, about 2 hours (`SKIP_LLM=1` skips it); if
   vLLM cannot install on the machine, the stage says so and nothing before it changes;
10. one packed file: `== send this one file back: results/gpu/omni-gpu-<stamp>.tar.gz`, with the label each table chose
   by rule.

To stop everything at any moment: `sudo python3 tools/omni_switch.py off` turns every Omni-Compass governor off and
hands the card back to its own settings.

Do not start it twice and do not use the card for anything else while it runs.

## 5. Bring the results back

Download `results/gpu/omni-gpu-<stamp>.tar.gz` (in JupyterLab: right-click, Download; or `scp` from your own computer).
It holds every raw reading, every table, the verdict and the checksums. **Then shut the rented machine down** on the
rental site, so the billing stops.

## 6. Read it before you believe it

Open `results/gpu/run-<stamp>/GPU_REPS.md` and check the rows of the manual's section 8.5 (*Wired right or wired
wrong*): watch equal to native, requests equal, the card's busy clock under Omni at or above its own, the lid while busy
at or above its own busy draw, fail-up rare in the credit-per-write table. If a row reads wired wrong, the run says
nothing about Omni-Compass until the wiring is fixed (`DISCLOSURES.md`, section 3).

## Before any machine: the simulated card

`python3 tools/gpu_physics_sim.py --out results/gpu/sim/after` runs Omni's own GPU governor, with its current
settings, against a modelled card for 10 paired repetitions in about two minutes. No GPU is needed. Every number it
prints comes from the card model, not from a meter, so it is a preview of what the governor does and never the result.
`results/gpu/sim/before` holds the same run with the settings before the share floor and busy gate were added.

## What you will get

A table from the GPU's own power meter:
- native against Omni watching only, and native against Omni governing;
- the preregistered primary result: work per energy, in requests served per kilojoule, with its 95% interval.

It ends with one verdict line, one of:
- **better, proven**;
- **worse, proven**;
- **not proven**;
- **better on energy, fails the service guardrail**.

Whatever it says is the answer, and it is the first number in this project that Omni-Compass's own code did not
compute.
