import sys, json, random; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2]))
import numpy as np
from dataclasses import replace
import omnicompass.adapter as AD
from benchmarks.stack_benchmark import simulate
from omnicompass import stack_sim as S
cfg=S.ManagerBenchmarkConfig(profile="full",scenarios=40,steps=72)
SC=S._mom_generate_scenarios(cfg,1000)[:40]+S._mom_generate_scenarios(cfg,2000)[:40]
R={json.loads(l)['i']:json.loads(l) for l in open('SEARCH_81.jsonl')}
base=R[12]; BASEP=AD.STACK_PARAMS; BASEA=AD.ASSIMILATION
K=['energy_kwh','time_healthy','recovery_minutes','violation_backlog','sla_violation_physical','availability','invariant_violations_ex_power','machine_round_trips','scale_reversals','thermal_travel']
rng=random.Random(7); out=open('REFINE_61.jsonl','w')
for i in range(61):
    law=dict(base['law']); eng=dict(base['engine']); a=base['assimilation']
    if i>0:
        law['down_dwell']=rng.randint(4,10); law['down_band']=rng.randint(3,6); law['down_after_add']=rng.randint(2,8)
        law['up_max']=rng.choice([1,2,3]); law['kq']=base['law']['kq']*rng.uniform(0.6,1.2)
        law['rho0']=min(0.95,base['law']['rho0']*rng.uniform(0.97,1.03)); law['kE']=base['law']['kE']*rng.uniform(0.5,1.5)
        a=base['assimilation']*rng.uniform(0.6,1.1)
    AD.STACK_PARAMS=replace(BASEP,**eng); AD.ASSIMILATION=a
    X=[simulate(s,'omni_k8s_throughput',cfg,AD.AllocationLaw(**law)) for s in SC]
    AD.STACK_PARAMS=BASEP; AD.ASSIMILATION=BASEA
    out.write(json.dumps({"i":i,"law":law,"engine":eng,"assimilation":a,"m":{k:float(np.mean([x[k] for x in X])) for k in K}})+"\n"); out.flush()
