"""PC-private fixed test order. Never copy plan/truth to the RX board."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,hashlib,json
from common import ROOT,read,write,sha

def create(assets,start_ns,slot_seconds=6,count_per_class=1):
 if slot_seconds<4:raise ValueError('slot >=4 seconds required')
 if count_per_class not in (1,10):raise ValueError('count per class must be 1 (smoke) or 10 (regression)')
 doc=read(assets/'manifest_240.json' if (assets/'manifest_240.json').exists() else assets/'manifest_24.json')
 rows=[];counts={i:0 for i in range(24)}
 for r in doc['records']:
  label=int(Path(r['file']).stem.split('_')[0])
  if counts[label]<count_per_class:rows.append(r);counts[label]+=1
 if len(rows)!=24*count_per_class:raise ValueError('balanced source set unavailable')
 labels=set();out=[]
 for i,r in enumerate(rows):
  label=int(Path(r['file']).stem.split('_')[0]);labels.add(label)
  p=assets/r['file']
  if p.parent.resolve()!=assets.resolve() or sha(p)!=r['source_sha256']:raise ValueError('asset identity')
  t=start_ns+int(i*slot_seconds*1e9)
  out.append(dict(opportunity=i,label=label,file=r['file'],source_sha256=r['source_sha256'],
                  start_ns=t,end_ns=t+int((slot_seconds-1)*1e9)))
 if labels!=set(range(24)):raise ValueError('24 distinct classes required')
 return dict(kind='GAIN_REPEAT_FIXED_SOURCE_PARAMETER_TEST',version=1,rows=out,count_per_class=count_per_class,
             start_ns=start_ns,end_ns=start_ns+int(len(rows)*slot_seconds*1e9),
             slot_seconds=slot_seconds,selection='nearest raw capture midpoint to slot midpoint; prediction independent',
             margin_ns=500_000_000,tx_gain_db=-40,tx_repeats=8,fs_hz=2560000,bw_hz=18000000)
def main():
 p=argparse.ArgumentParser();p.add_argument('--start-pc-ns',type=int,required=True)
 p.add_argument('--out',type=Path,required=True);p.add_argument('--slot-seconds',type=int,default=6)
 p.add_argument('--count-per-class',type=int,choices=[1,10],default=1)
 a=p.parse_args();plan=create(ROOT/'tx/assets',a.start_pc_ns,a.slot_seconds,a.count_per_class)
 # exclusive output prevents replacing the predeclared denominator/order
 with a.out.open('x',encoding='utf8') as f:json.dump(plan,f,indent=2)
 print('PLAN_FROZEN_SHA256='+sha(a.out));print('DURATION_SECONDS='+str(len(plan['rows'])*a.slot_seconds))
if __name__=='__main__':main()
