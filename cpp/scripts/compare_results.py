import csv,json,math,sys
from pathlib import Path
if len(sys.argv)!=4: raise SystemExit('usage: compare_results.py expected.csv actual.csv report.json')
e=list(csv.DictReader(open(sys.argv[1],newline='',encoding='utf-8'))); a=list(csv.DictReader(open(sys.argv[2],newline='',encoding='utf-8')))
exact={'run_id','target_sign','born','convey','convey_start','convey_confirm','cert','cert_start','cert_complete','max_streak','actuator_saturated_periods'}
mis=[]; ma=mr=0.0
if len(e)!=len(a): mis.append({'kind':'row_count','expected':len(e),'actual':len(a)})
for i,(x,y) in enumerate(zip(e,a)):
 for k,v in x.items():
  if k in exact:
   if v!=y.get(k):mis.append({'row':i,'column':k,'expected':v,'actual':y.get(k)})
  else:
   xv=float(v); yv=float(y[k]); ae=abs(xv-yv); re=ae/max(abs(xv),abs(yv),1e-300);ma=max(ma,ae);mr=max(mr,re)
   if not (ae<=5e-12 or re<=5e-11):mis.append({'row':i,'column':k,'expected':xv,'actual':yv,'abs':ae,'rel':re})
  if len(mis)>=100:break
 if len(mis)>=100:break
r={'rows_expected':len(e),'rows_actual':len(a),'max_abs_error':ma,'max_rel_error':mr,'mismatches_capped':len(mis),'pass':not mis,'tolerances':{'abs':5e-12,'rel':5e-11},'first_mismatches':mis[:20]}
Path(sys.argv[3]).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(0 if r['pass'] else 1)
