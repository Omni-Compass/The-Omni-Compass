#!/usr/bin/env python3
"""Paired same-tower experiment: native stack / Omni observe / Omni authority ON."""
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from benchmarks.stack_benchmark import run
from omnicompass.adapter import AllocationLaw
KEYS=['availability','time_healthy','recovery_minutes','recovered','energy_kwh','sla_violation_physical','sla_violation_total','violation_backlog','violation_power','violation_heat','contradictions','peak_power_kw','node_hours','idle_node_hours','machine_round_trips','scale_reversals']
def main():
 p=argparse.ArgumentParser(); p.add_argument('--runs',type=int,default=100); p.add_argument('--seed',type=int,default=360555127); p.add_argument('--out',default='results/tower_off_on'); a=p.parse_args()
 out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
 s=run(a.runs,a.seed,out,AllocationLaw(),arms=['k8s_ref_70','omni_k8s_observe','omni_k8s_throughput'])
 b=s['means']['k8s_ref_70']; o=s['means']['omni_k8s_observe']; c=s['means']['omni_k8s_throughput']
 ident={k:abs(float(b[k])-float(o[k])) <= 1e-12 for k in KEYS}
 receipt={'runs':a.runs,'seed':a.seed,'same_tower_observe_identity':all(ident.values()),'identity_by_metric':ident,'off':{k:b[k] for k in KEYS},'on':{k:c[k] for k in KEYS}}
 (out/'TOWER_OFF_ON_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
 print(json.dumps(receipt,indent=2))
if __name__=='__main__': main()
