# Running the GPU test yourself, step by step

This gets the first real-meter result for Omni-Compass. It costs roughly $10 to $25 in rented GPU time. You type a
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

The repository is private, so GitHub needs a key:

1. On github.com go to **Settings → Developer settings → Personal access tokens → Fine-grained tokens**.
2. Create a token with **read-only** access to this one repository. Copy it.

Then on the rented machine:

```bash
git clone -b claude/kubernetes-clusters-docker-stack-gp26ve https://<YOUR-GITHUB-NAME>:<TOKEN>@github.com/Omni-Compass/the-omni-compass omni
cd omni
pip install numpy          # PyTorch is already on the machine
nvidia-smi                 # should show your GPU
```

## 4. The trial run (about 40 minutes)

This checks that everything works on your machine. It is never published.

```bash
sudo REPS=2 DURATION=300 bash scripts/gpu_paired.sh
```

At the end it prints a table. What matters here:
- It doesn't say **INVALID**.
- The *Omni governs* column shows power-limit writes.
- The watch arm shows zero writes.

## 5. The real test (about 6 hours)

The code is frozen, with 10 repetitions, exactly as fixed in `docs/GPU_PREREGISTRATION.md`. Don't change anything
between the trial and this.

```bash
sudo PHASE=confirm nohup bash scripts/gpu_paired.sh > confirm.log 2>&1 &
```

`nohup ... &` keeps it running if your connection drops. You can close the window and come back. To check on it:

```bash
tail -5 confirm.log
```

## 6. Bring the results back

When `confirm.log` ends with the table:

```bash
sudo tar czf gpu_results.tgz results/gpu
```

Then, from your own computer (a new Terminal window, not the rented machine):

```bash
scp ubuntu@123.45.67.89:omni/gpu_results.tgz .
```

Send that file to Claude, or keep it. It holds every raw reading, the table, the verdict and checksums.

**Then shut the rented machine down** on the rental site, so the billing stops.

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
