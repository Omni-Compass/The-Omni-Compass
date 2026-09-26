import sys, json, random; sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2]))
import numpy as np
from dataclasses import replace
import omnicompass.adapter as AD
from benchmarks.stack_benchmark import simulate
from omnicompass import stack_sim as S
cfg=S.ManagerBenchmarkConfig(profile="full",scenarios=40,steps=72)
SC=S._mom_generate_scenarios(cfg,1000)[:40]+S._mom_generate_scenarios(cfg,2000)[:40]
BASEP=AD.STACK_PARAMS; BASEA=AD.ASSIMILATION
K=['energy_kwh','time_healthy','recovery_minutes','violation_backlog','sla_violation_physical','availability','invariant_violations_ex_power','machine_round_trips','scale_reversals','thermal_travel']
def run(law_kw, eng_kw, assim, arm):
    AD.STACK_PARAMS=replace(BASEP, **eng_kw); AD.ASSIMILATION=assim
    R=[simulate(s,arm,cfg,AD.AllocationLaw(**law_kw)) for s in SC]
    AD.STACK_PARAMS=BASEP; AD.ASSIMILATION=BASEA
    return {k:float(np.mean([r[k] for r in R])) for k in K}
rng=random.Random(20260923)
out=open('SEARCH_81.jsonl','w')
arm=sys.argv[1] if len(sys.argv)>1 else 'omni_k8s_throughput'
for i in range(81):
    if i==0: law_kw,eng_kw,assim={}, {}, BASEA
    else:
        law_kw=dict(rho0=rng.uniform(0.80,0.95),rho_min=rng.uniform(0.50,0.70),kI=rng.uniform(0,0.3),kE=rng.uniform(0,0.5),kq=rng.uniform(0.2,1.0),
                    margin=rng.uniform(0.0,0.3),cap_min=rng.uniform(0.65,0.85),down_band=rng.randint(1,5),down_dwell=rng.randint(2,8),
                    down_after_add=rng.randint(0,4),U_gate=rng.uniform(0.4,0.7),up_max=rng.choice([2,3,4]))
        eng_kw=dict(mu=rng.uniform(2,6),alpha_E=rng.uniform(2,6),lambda_I=rng.uniform(0.5,2.0),delta=rng.uniform(0.2,0.8))
        assim=rng.uniform(0.2,0.5)
    m=run(law_kw,eng_kw,assim,arm)
    out.write(json.dumps({"i":i,"law":law_kw,"engine":eng_kw,"assimilation":assim,"m":m})+"\n"); out.flush()
