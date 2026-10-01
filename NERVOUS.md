# Nervous system

Omni-Compass is one field. Muscles are nerves.

```
telemetry  ->  afferent (per muscle)
           ->  one six-state engine
           ->  reflex (shield)
           ->  efferent (only WIRED + authority + not killed)
           ->  native controller on kill
```

`omnicompass/nervous.py` is the register. It does not invent GPU or chiller physics.

| Status | Meaning |
|---|---|
| wired | this tree can sense and push |
| sensed | this tree can sense; it does not push |
| open | named, no plant, no push |

Wired today: `nodes`, `hpa`, `power_cap`.  
Sensed: `heat`, `network`, `security`.  
Open: GPU, cooling, grid, queues, agents, …  
Never a muscle: value alignment.

```bash
python k8s_controlplane/test_nervous.py
```
