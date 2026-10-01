# Proven. Nothing else.

Object under test: Omni-Compass six-state engine + documented HPA replica law.
Input: PlanetLab/CoMon 2011 VM CPU percent, hold-last to 15 s.
Not a Kubernetes cluster. Not metrics-server. Not kube-controller-manager.

## Shown

1. Two independent HPA v2 replica implementations, same recorded series:
   51840 / 51840 identical `desiredReplicas`.
2. Omni observe does not change that HPA path: 9 / 9 traces.
3. Engine state `(E, U, I_U, S, B)` finite on every step: 51840 / 51840.
4. Push magnitude bounded: 51840 / 51840.
5. Evolved `S` stayed at or above `S−`: 51840 / 51840.
6. On these series mean CPU metric = 0.086. HPA target 0.70. Replica changes per 24 h trace = 0.89. Omni `ρ*` range 0.832–0.914.
7. Open-loop energy on the same series: HPA@70, Omni-observe, and Omni-target all 14.47 kWh. HPA@50 = 21.24 kWh.
8. 15 s discrete plant (synthetic): Omni observe bit-identical to HPA+CA on 24 / 24 scenarios. Omni writing node-down on that plant thrashed (88 starts / 84 stops vs 21.5 / 12.9).

## Not shown

No live object. No live `status.desiredReplicas`. No live node pool. No energy or SLO claim against a cluster. Those sentences are not claims.
