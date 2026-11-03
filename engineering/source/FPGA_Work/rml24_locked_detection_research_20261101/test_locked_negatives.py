import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,numpy as np
p=Path(__file__).parent;sys.path.insert(0,str(p));sys.path.insert(0,'E:/FPGA_Work/rml24_visual_review_fix_20261031/candidate/rml24_final/recovery')
from locked_detector import detect_locked
import candidate_two_dc as rec
rng=np.random.default_rng(171928);n=np.arange(65536);rows=[]
for i in range(48):
 kind=('noise','cw','dc','random_psk')[i%4]
 if kind=='noise':z=rng.normal(size=len(n))+1j*rng.normal(size=len(n))
 elif kind=='cw':z=100*np.exp(2j*np.pi*rng.uniform(-1200000,1200000)*n/2560000)
 elif kind=='dc':z=np.full(len(n),100+50j)
 else:z=100*np.exp(1j*np.pi/2*rng.integers(0,4,len(n)))
 z=z+.1*(rng.normal(size=len(n))+1j*rng.normal(size=len(n)))
 d=detect_locked(z,rec.train);accepted=d['score']>=.1 and abs(d['coarse_cfo_hz'])<=1000;recovered=False
 if accepted:
  try:rec.recover(z);recovered=True
  except RuntimeError:pass
 rows.append(dict(kind=kind,detected=accepted,strict_recovered=recovered,score=d['score'],cfo_hz=d['coarse_cfo_hz']))
(p/'LOCKED_HARD_NEGATIVES.json').write_text(json.dumps(dict(scope='48 synthetic negatives; no operational false alarm rate claim',accepted=sum(r['detected'] for r in rows),strict_false_recoveries=sum(r['strict_recovered'] for r in rows),rows=rows),indent=2));print('HARD_NEGATIVES',sum(r['detected'] for r in rows),sum(r['strict_recovered'] for r in rows))
