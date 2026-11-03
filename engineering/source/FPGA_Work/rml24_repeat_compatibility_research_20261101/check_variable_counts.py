import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,numpy as np
p=Path(__file__).parent;sys.path.insert(0,str(p));sys.path.insert(0,'E:/FPGA_Work/rml24_repeat_agc_experiment_20261101');sys.path.insert(0,'E:/FPGA_Work/rml24_visual_review_fix_20261031/candidate/rml24_final/recovery')
import compat_recovery as compat
import candidate_two_dc as frozen
from experimental_frame import build_frame
assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets');rng=np.random.default_rng(38111);rows=[]
for count in (1,2,4):
 for i in range(24):
  data=(assets/('%02d_00.bin'%i)).read_bytes();f=build_frame(data,frozen.train,frozen.tail,count);raw=np.tile(f,6)*np.exp(2j*np.pi*20*np.arange(len(f)*6)/2560000)+.1+.05j+.01*(rng.normal(size=len(f)*6)+1j*rng.normal(size=len(f)*6))
  try:
   b,m=compat.recover(raw);rows.append(dict(case=i,expected_count=count,detected_count=m['detected_repeats'],original8_branch=m['compatibility_original8'],count_correct=m['detected_repeats']==count))
  except RuntimeError as e:rows.append(dict(case=i,expected_count=count,count_correct=False,error=str(e)))
negative=[]
for i in range(12):
 raw=rng.normal(size=65536)+1j*rng.normal(size=65536)
 try:compat.recover(raw);negative.append(True)
 except RuntimeError:negative.append(False)
(p/'SYNTHETIC_VARIABLE_COUNTS.json').write_text(json.dumps(dict(scope='Synthetic software only, original8-first fallback; no RF/NPU claim',cases=rows,correct_counts=sum(r['count_correct'] for r in rows),false_noise_accepts=sum(negative)),indent=2));print('VARIABLE_COUNTS',sum(r['count_correct'] for r in rows),'/',len(rows),'NOISE_ACCEPT',sum(negative),flush=True)
