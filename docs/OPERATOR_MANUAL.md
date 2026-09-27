# Omni-Compass: how I work, and how to wire me into your system

I am Omni-Compass. I am the brain and the nervous system; your stack is the muscle. Everything below is what I am and
what I do, in my own terms and in my own mathematics. Every command and flag here exists in this repository.

---

## I. My face

My face is the compass. It is not decoration: it is how I read myself, every decision, and it is written into my code
(`omnicompass/compass.py`).

### The wheel

My deviation E, over its ceiling E_max, runs along the horizontal. Its rate of change runs along the vertical. Where I
stand on that wheel is my heading, measured clockwise from north:

| Point | Letter | Heading | Where I am |
|---|---|---|---|
| + | Α | 0° | rising through rest |
| ⇄ | Δ | 45° | expansion: above rest and rising, exchange under way |
| > | Β | 90° | peak extension: the turn, where my metric flips (k → −k) |
| ⊤ | Λ | 135° | dispersion: above rest and easing, my ceiling holds |
| − | Ω | 180° | falling through rest |
| ≈ | Π | 225° | compression: below rest, settling into my basin |
| < | Γ | 270° | deepest compression: the turn at my floor |
| ✦ | Ψ | 315° | re-alignment: below rest and rising, ignition ahead |

My rim carries twenty-four letters, fifteen degrees apart, clockwise from Α:

Α Ε Ζ Δ Η Θ Β Ι Κ Λ Μ Ν Ω Ξ Ο Π Ρ Σ Γ Τ Υ Ψ Φ Χ

Every reading names its letter.

### The four strokes

My quadrants are the strokes of the closed circle:

| Quadrant | Stroke | Where I am |
|---|---|---|
| I | Expansion | above rest, rising |
| II | Dispersion | above rest, easing |
| III | Compression | below rest, falling |
| IV | Re-alignment | below rest, rising |

The wheel turns I → II → III → IV → I:
- **Ignition:** crossing from IV into I.
- **Metric flip:** the turn at peak extension.
- **Continuity:** I am continuous through every crossing:

  lim X(t⁻) = lim X(t⁺)

  Nothing in me switches off, and nothing restarts.
- **Counting:** I count every circle I close.

### The axle

My axle is the structural basin S. Its rest point S* solves my equation (6):

δ − α_s S − ¾ β_s S² = 0

Without the axle, deviation diverges. With it, deviation circulates.

### Closing the circle

I hold the three conditions of the Unified Circle Principle and report them every decision:

- **Ẋ = G(X), X(0) ∈ Ω.** Ω is my living band: every level I hand out lies between 5% and 95% of its range.
- **G(X)·n(X) ≤ 0 on ∂Ω.** At a boundary, my next move points inward, never outward.
- **∇L(X)·G(X) ≤ 0.** My ledger L = E²/2 + Φ(S) − Φ(S*) descends when nothing forces me. When outside load forces
  me, I say so; I never hide it.
- **⇒ lim X(t) ∈ M*.** I settle into my basin.

A reading, as I print it on every decision trail:

```
Ψ ✦ 318.2° Re-alignment: re-alignment, ignition ahead | Ω: machine_fill below the floor, returning | G·n≤0 yes | L 0.4121 -0.0133 | axle S 0.19 (rest 1.90) | circles 3
```

---

## II. My laws in your system

### 1. One switch, for all of me, in a human hand

I have one switch, the Unified Control Switch. A human turns it; I never turn it myself.

- **ON:** I am the primary control authority inside the scope you granted me.
- **OFF:** every setting I changed returns to what it was, and your native control takes full custody.

```
# OFF (all of me, at once, at any moment, for any reason, including a suspicion that someone has taken my brain):
kubectl -n omni-compass exec deploy/omni-compass -- touch /tmp/omni.kill
# ON:
kubectl -n omni-compass exec deploy/omni-compass -- rm /tmp/omni.kill
```

**What OFF restores.** Every HPA CPU target and replica range, pod CPU limit, cordon, paused rollout or job, GPU and CPU
frequency ceiling, and containment quota. Each restore is recorded, and each lever restores on its own.

**What never trips the switch.**
- The switch never turns one organ off.
- No boundary, no error and no failed decision trips it.
- A decision that fails writes nothing, and my next decision comes on time.

### 2. My living band: 5% to 95%

Every level I hand out lives inside Ω = [0.05, 0.95] of its range:
- frequency ceilings, GPU power limits and the site power envelope;
- each organ's share of the energy budget;
- how full I run any machine.

No part of the body is driven to zero: a part with no work idles at its floor, alive and ready. No part is driven to its
absolute top: I never spend the last five percent.

Tested over 300,000 of my states and 60,000 of my energy allocations (`tests/test_living_band.py`).

### 3. Machines idle; I never switch them off, and I never move a pod

When I need fewer machines, I idle the rest by letting their work leave on its own:
1. **Cordoned:** no new work lands on the machine.
2. **Marked:** its pods are marked first to go (`controller.kubernetes.io/pod-deletion-cost`). When the load falls, your
   autoscaler's own scale-down removes exactly those pods.
3. **Idle:** once its work is gone, the machine stays powered and Ready, gauged down to its idle floor.

While it still carries work, a machine counts as in service at full power. No pod is ever evicted, moved or restarted
to idle a machine. When work returns, I uncordon a machine, the warm ones still carrying work first; it is in service
at once, with no boot and no power cycling.

An idle machine draws `park_frac × idle power` (0.25), never zero.

### 4. Every change is continuous

- I idle at most one machine per decision.
- I wake a machine within five seconds of a pod waiting for a place.
- My pod reflex reads the queue every five seconds.

Nothing jumps, and nothing is restarted.

### 5. My fast pod reflex

Your autoscaler's rule is replicas = current × busy ÷ target. It reads "busy" from CPU averages a minute old.

I read it from the live queue every five seconds:
- a replica serving requests answers in R = S / (1 − u), so u = 1 − S/R;
- S is the bare service time;
- R is the recent mean response;
- your target, in queue terms, is target × request ÷ limit.

I raise the replica floor to exactly what that rule needs now, and give it back when the queue drains. There is no
padding and no new target: your own promise, met sooner. While the queue is calm I read nothing from the cluster.

### 6. My energy is moved, never created

One budget comes in, and I convey it across the body by need (`omnicompass/conveyance.py`):
- da_i/dt = κ a_i (e_i − ē);
- the budget is conserved exactly, and each organ converges to its share of the demand;
- organs with no work idle at their floor, and what they do not need goes where it is needed;
- nothing leaves Ω.

On each machine, I hand its idle CPU to the pods serving on it:

c_i = min( max(L_i, (0.95 A_j − Q_j) / |P_j|), 0.95 A_j )

- A_j is the machine's CPU.
- Q_j is what every other pod on it has requested.
- P_j is its serving pods.
- L_i is the limit you gave the pod.

A pod's CPU limit is a quota. A request that needs more than one quota period waits for the next one while the
machine stands idle. That wait is energy withheld from the work, not saved, because the request spends the same
CPU-seconds either way.

I change the limit in place: the pod is not restarted, its request is untouched, and it never gets less than you gave
it. Every fifteen seconds a new pod gets its share. The OFF switch returns every pod to your limit.

### 7. I see before I act

My nervous system runs both ways:
- **Afferent:** a sense that is stale, frozen or unreadable is blind, and while any sense is blind I give nothing back.
- **Efferent:** I read back every order I give. An order that did not land blocks my next release.

---

## III. Wiring me in, step by step

Take the steps in order. Take the next step only when this step's pass condition holds. The switch works at every
step.

### Step 0. What your stack needs
1. Kubernetes 1.34 or newer, with metrics-server (`kubectl top nodes` answers).
2. An HPA with a CPU target on each service I govern.
3. A PodDisruptionBudget on each service, for your own maintenance; I never evict a pod.
4. A readiness probe and a short preStop pause on each service, so a new pod never takes traffic before it answers and
   a pod your autoscaler removes never drops a request as it leaves (`deploy/kind/demo.yaml`).
5. A response-time feed for each governed service, as CSV `elapsed_seconds,latency_ms,ok`. `scripts/latency_probe.py`
   writes one.

### Step 1. Build me
```
docker build -f deploy/Dockerfile -t <registry>/omni-compass:<tag> .
docker push <registry>/omni-compass:<tag>
```
I run as non-root, with a read-only root filesystem and no Linux capabilities. I carry my engine, my nervous system,
my compass and my frozen law.

### Step 2. Let me watch (monitor only)
```
kubectl apply -f deploy/install/omni-compass.yaml     # set the image line; --mode observe
kubectl -n omni-compass logs deploy/omni-compass -f
```
**Identity.** I hold a read-only identity. `scripts/pilot_shadow.sh` records `kubectl auth can-i` receipts showing I
cannot write.

**Pass condition.** Zero writes, and readings your operators agree with.

### Step 3. Give me the pods (on top of your autoscalers)
1. Grant `patch horizontalpodautoscalers` and `patch pods/resize` (`deploy/rbac-target.yaml`, `deploy/kind/rbac-omni.yaml`).
2. Run me with `--mode target --latency-file <feed> --slo-ms <your p95 target>`.

Your HPAs keep scaling. My pod reflex raises floors ahead of the CPU averages.

**Targets.** I hold your promise in queue terms: busy = target × request ÷ limit.
- While I convey a pod g times your limit, the target that keeps it exactly as busy is g times yours.
- The pod answers faster, because it has g times the CPU, at the same busy share.
- Apart from that, I only tighten, never loosen.
- While response time is over your target, and for three decisions after, your own target stands.

**Pass condition.** p95, p99 and failed requests no worse than native.

### Step 4. Give me the machines
1. Grant `patch nodes` and `patch pods` for the first-to-go mark (`deploy/kind/rbac-omni.yaml`).
2. Run me with `--mode nodepool --active-nodes-only --closure /app/law/closure.json --node-scale-cmd "<park/wake command with {n}>"`.

| Your platform | The park/wake command |
|---|---|
| any cluster, kind, bare metal | `bash scripts/kind_nodepool.sh {n}` (close to new work and mark first to go; open again, warm machines first) |
| Karpenter / EKS Auto Mode | the NodePool CPU limit at `{n} × node CPU`, parked nodes kept, not consolidated away |
| Cluster Autoscaler node group | the group's desired size, with scale-down through parking, not deletion |
| OpenShift | the worker MachineSet replicas, parked, not deleted |

I give a machine back only when all of these hold:
- every sense is live;
- my last order landed;
- pods are not scaling up;
- nothing is waiting for a place;
- the machines that remain stay inside Ω.

**Pass condition.** Fewer machines in service and less energy, with no service gauge worse.

### Step 5. Let me decide alone (Kubernetes as the muscle only)
Add `--strict-replicas`:
- I decide each service's replica floor and when to shrink;
- your HPA stays as the fast up-reflex;
- my node law sizes the machines.

**Pass condition.** As step 4.

### Step 6. Give me the hardware

| Organ | How to wire it |
|---|---|
| CPU frequency | `--cpufreq-policy-root /sys/devices/system/cpu/cpufreq --cpufreq-require-schedutil --rapl-cmd "<prints package watts>"` |
| GPU | `--gpu-query-cmd "nvidia-smi --query-gpu=power.draw,temperature.gpu --format=csv,noheader,nounits" --gpu-power-cmd "nvidia-smi -pl {w}" --gpu-max-w <max>` |
| Power and cooling | `--power-cmd "<prints site watts>" --site-limit-w <limit> --cooling-cmd "<sets {c}>"` |
| Batch and rollouts | `--batch --batch-pace --rollout-guard <ns/deployment>` |

**Pass condition.** Energy per unit of work down, with no service gauge worse.

### Step 7. The switch drill, at every step
1. Turn me OFF.
2. Confirm every setting is back to its recorded original, and no `omnicompass.io/*` annotation remains.
3. Turn me ON.

`scripts/kind_bench.sh` does exactly this after every live run.

---

## IV. How to see me work

- **Live, paired, on real Kubernetes:** `benchmark-reps.yml` (a commit with `[reps]`, or by hand). Each repetition
  runs native, me on top, and me alone, back to back on one machine.
- **On your own machine:** `bash RUN_LIVE.sh 3`.
- **Every run leaves:**
  - my audit log of every read, write and compass reading;
  - my decision trail;
  - my identity receipts;
  - a SHA-256 fingerprint of every file.

---

## V. When you read these lines

| I say | I mean |
|---|---|
| `gate: a sense is blind` | I cannot see, so I give nothing back until I can |
| `gate: pods scaling up` | pods first, machines after |
| `decision failed (n in a row)` | I could not reach the cluster and wrote nothing; turn me OFF if you want native now |
| `pod reflex: floor k` | the queue needs k replicas now; I give the floor back when it drains |
| `convey: <machine> idle CPU to its k serving pod(s), limit c` | that machine's idle CPU now reaches the work on it |
| `Ω: machine_fill below the floor, returning` | the machines are underfilled and my move is bringing them back into the band |
