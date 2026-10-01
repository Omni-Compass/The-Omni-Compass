import sys, json, random; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2]))
import numpy as np
from dataclasses import replace
import omnicompass.adapter as AD
import benchmarks.stack_benchmark as B
from omnicompass import stack_sim as S
cfg=S.ManagerBenchmarkConfig(profile="full",scenarios=40,steps=72)
SC=S._mom_generate_scenarios(cfg,1000)[:40]+S._mom_generate_scenarios(cfg,2000)[:40]
K=['energy_kwh','time_healthy','recovery_minutes','violation_backlog','sla_violation_physical','availability','invariant_violations_ex_power','scale_reversals','machine_round_trips','thermal_travel']
BASE_OVR=dict(kI=0.05,kE=0.40,cap_min=0.65,down_band=1,down_dwell=10,down_after_add=3,kq=0.30,U_gate=0.45)
FIXED=dict(backlog_release=True,power_ceiling=9.0,power_ceiling_backlog=9.0,spread_step=0.0,B_cap=9.0,size_at_full_cap=True)
rng=random.Random(99); out=open('JOINT_121.jsonl','w')
for i in range(121):
    if i==0: ovr=dict(BASE_OVR); pr=9.0; extra={}
    elif i==1: ovr=dict(BASE_OVR); pr=0.01; extra={}
    else:
        ovr=dict(kI=rng.uniform(0,0.3),kE=rng.uniform(0.1,0.6),cap_min=rng.uniform(0.65,0.80),down_band=rng.randint(1,5),down_dwell=rng.randint(1,12),
                 down_after_add=rng.randint(0,6),kq=rng.uniform(0.2,1.0),U_gate=rng.uniform(0.35,0.65))
        pr=rng.choice([0.005,0.0075,0.01,0.015,0.02,0.03])
        extra=dict(rho0=rng.uniform(0.86,0.95),rho_min=rng.uniform(0.55,0.72),margin=rng.uniform(0.0,0.15),up_max=rng.choice([2,3,4]))
    B.mode_law=lambda mode,base=None,ovr=ovr,pr=pr: replace(base or AD.AllocationLaw(), **FIXED, **ovr, push_release=pr)
    law=AD.AllocationLaw(**extra)
    X=[B.simulate(s,'omni_k8s_throughput',cfg,law) for s in SC]
    out.write(json.dumps({"i":i,"ovr":ovr,"push_release":pr,"extra":extra,"m":{k:float(np.mean([x[k] for x in X])) for k in K}})+"\n"); out.flush()
