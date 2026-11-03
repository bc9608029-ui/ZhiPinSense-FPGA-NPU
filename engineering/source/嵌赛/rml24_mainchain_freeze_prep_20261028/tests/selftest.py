#!/usr/bin/env python3
import json, subprocess, sys
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
d=ROOT/'tests'/'selftest_work'; d.mkdir(exist_ok=True)
rows=[{"index":i,"label":i%2,"pred":i%2} for i in range(240)]
base={"run":"x","denominator":240,"correct":240,"missing":0,"rows":rows}
for n in ('bf','bs','cf','cs'):(d/f'{n}.json').write_text(json.dumps(base),encoding='utf-8')
p=subprocess.run([sys.executable,str(ROOT/'scripts/audit_scores.py'),str(d/'bf.json')],capture_output=True,text=True); assert p.returncode==0
p=subprocess.run([sys.executable,str(ROOT/'scripts/promotion_gate.py'),'--baseline-fixed',str(d/'bf.json'),'--baseline-scan',str(d/'bs.json'),'--candidate-fixed',str(d/'cf.json'),'--candidate-scan',str(d/'cs.json'),'--out',str(d/'o.json')]); assert p.returncode==0
bad=dict(base); bad['correct']=239; bad['rows']=list(rows); bad['rows'][0]=dict(bad['rows'][0],pred=1)
(d/'cf.json').write_text(json.dumps(bad),encoding='utf-8')
p=subprocess.run([sys.executable,str(ROOT/'scripts/promotion_gate.py'),'--baseline-fixed',str(d/'bf.json'),'--baseline-scan',str(d/'bs.json'),'--candidate-fixed',str(d/'cf.json'),'--candidate-scan',str(d/'cs.json'),'--out',str(d/'o2.json')]); assert p.returncode==2
iq=np.array([[100,200],[-300,400],[0,0]],dtype='<i2'); iq.tofile(d/'raw.i16'); iq.tofile(d/'rec.i16')
p=subprocess.run([sys.executable,str(ROOT/'scripts/analyze_iq_triplet.py'),'--raw',str(d/'raw.i16'),'--recovered',str(d/'rec.i16'),'--out',str(d/'iq.json')]); assert p.returncode==0
q=json.loads((d/'iq.json').read_text()); assert q['raw_vs_recovered']['corr']>0.999999
print('MAINCHAIN_SELFTEST result=PASS checks=4')
