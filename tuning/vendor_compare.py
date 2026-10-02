# SPDX-License-Identifier: LicenseRef-OmniCompass-Evaluation-1.0
# Copyright (c) 2026 The Omni-Compass LLC. Evaluation and simulation use only; any other use requires a signed, paid
# Omni-Compass Enterprise License. See LICENSE.
"""Named products vs Omni-Compass on the fleet plant with the response-time gauge (fleet/sim_slo.py), development seeds.
Vendor arms emulate documented behaviour (see fleet/sim_slo.py VENDOR notes); they are not the vendors' binaries."""
import sys, json; sys.path.insert(0,'.')
import numpy as np
from multiprocessing import Pool
from fleet import sim_slo; from fleet.harness import make_scenario
from tuning.speed_search import gauges, LOWER, HIGHER
from omnicompass.speed import SpeedLaw
R=json.load(open('tuning/SPEED_SEARCH_21.json'))
best={r['i']:r['cfg'] for r in R}
ARMS=['k8s_hpa70_ca','openshift','gke_optimize','aks_nap','turbonomic','omni_fleet','speed176','speed159']
def one(k):
    v,s=k; sc=make_scenario(v,s); out={}
    for a in ARMS:
        if a.startswith('speed'):
            c=best[int(a[5:])]; r=sim_slo.run(sc,'omni_speed',speed_law=SpeedLaw(**c['law']),omni_every=c['every'],lat_gain=c['lat_gain'],slo_mult=c['slo_mult'])
        else: r=sim_slo.run(sc,a)
        out[a]=gauges(r)
    return k,out
if __name__=='__main__':
    keys=[(v,s) for v in ('web','multi','batch','gpu') for s in (101,102,103,104)]
    with Pool(4) as p: res=dict(p.map(one,keys))
    out={v:{a:{m:float(np.mean([res[(v,s)][a][m] for s in (101,102,103,104)])) for m in LOWER+HIGHER} for a in ARMS} for v in ('web','multi','batch','gpu')}
    open('tuning/VENDOR_COMPARE_DEV.json','w').write(json.dumps(out,indent=1))
    for v in ('web','multi','batch','gpu'):
        print(v, ''.join(f'{a[:11]:>12}' for a in ARMS))
        for m in ['energy_kwh','node_hours','p95_ms','p99_ms','mean_ms','start_stop','node_reversals','work_completed','time_healthy']:
            print(f'  {m:15}'+''.join(f'{np.mean([res[(v,s)][a][m] for s in (101,102,103,104)]):12.4g}' for a in ARMS))
