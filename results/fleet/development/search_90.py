import sys, json, random; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[3]))
import numpy as np
from dataclasses import replace
from fleet.sim import run
from fleet.harness import make_scenario
from omnicompass.adapter import AllocationLaw, mode_law
DEV=[(v,s) for v in ('web','multi','batch','gpu') for s in (101,102,103,104)]
SC={k:make_scenario(*k) for k in DEV}
BASE={k:run(SC[k],'k8s_hpa70_ca') for k in DEV}
K=['energy_kwh','time_healthy','violation_backlog','violation_power','violation_heat','work_completed','machines_started','node_reversals']
rng=random.Random(6); out=open('SEARCH_90.jsonl','w')
thr=mode_law('throughput')
for i in range(90):
    kw=dict(rho0=rng.uniform(0.70,0.95),rho_min=rng.uniform(0.5,0.8),kI=rng.uniform(0,0.3),kE=rng.uniform(0,0.5),kq=rng.uniform(0.2,1.0),
            down_band=rng.randint(0,6),down_dwell=rng.randint(1,30),down_after_add=rng.randint(0,40),up_band=rng.randint(0,4),push_release=rng.uniform(0.01,0.12),
            cap_min=rng.uniform(0.65,0.9),margin=rng.uniform(0,0.2),U_gate=rng.uniform(0.4,0.9),up_max=rng.choice([2,4,8]))
    every=rng.choice([1,2,4,8])
    law=replace(thr,**kw)
    R={k:run(SC[k],'omni_single_throughput',omni_every=every,governor_law=law) for k in DEV}
    rel_e=float(np.mean([R[k]['energy_kwh']/BASE[k]['energy_kwh'] for k in DEV]))
    ok=all(R[k]['work_completed']>=BASE[k]['work_completed']-0.002 and R[k]['time_healthy']>=BASE[k]['time_healthy']-0.01
           and R[k]['violation_backlog']<=BASE[k]['violation_backlog']+0.01 and R[k]['node_reversals']<=BASE[k]['node_reversals']+2 for k in DEV)
    out.write(json.dumps({'i':i,'law':kw,'every':every,'rel_energy':rel_e,'ok':ok,
        'per_vessel':{v:{m:float(np.mean([R[(v,s)][m]/(BASE[(v,s)][m] if m=='energy_kwh' else 1) for s in (101,102,103,104)])) for m in K} for v in ('web','multi','batch','gpu')}})+'\n'); out.flush()
