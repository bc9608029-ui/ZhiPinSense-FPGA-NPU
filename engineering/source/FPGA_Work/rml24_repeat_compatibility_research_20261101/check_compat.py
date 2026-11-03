import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,numpy as np
p=Path(__file__).parent;sys.path.insert(0,str(p));sys.path.insert(0,'E:/FPGA_Work/rml24_repeat_agc_experiment_20261101');sys.path.insert(0,'E:/FPGA_Work/rml24_visual_review_fix_20261031/candidate/rml24_final/recovery')
import compat_recovery as compat
import candidate_two_dc as frozen
from experimental_frame import build_frame
assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets');rng=np.random.default_rng(38111);rows=[]
for i in range(24):
 data=(assets/('%02d_00.bin'%i)).read_bytes();f=build_frame(data,frozen.train,frozen.tail,8);raw=np.tile(f,4)*np.exp(2j*np.pi*20*np.arange(len(f)*4)/2560000)+.1+.05j+.01*(rng.normal(size=len(f)*4)+1j*rng.normal(size=len(f)*4))
 a,_=frozen.recover(raw);b,m=compat.recover(raw);rows.append(dict(case=i,original8_success=True,bit_exact=np.array_equal(a,b),count=m['detected_repeats']));assert np.array_equal(a,b)
negative=[]
for i in range(12):
 raw=rng.normal(size=65536)+1j*rng.normal(size=65536)
 try:compat.recover(raw);negative.append(True)
 except RuntimeError:negative.append(False)
(p/'SYNTHETIC_COMPAT_RESULT.json').write_text(json.dumps(dict(scope='Synthetic software only; not NPU/RF qualification; primary frozen recovery success returned unchanged',cases=rows,false_noise_accepts=sum(negative),noise_cases=len(negative)),indent=2));print('UNCHANGED_EIGHT_BRANCH',sum(r['bit_exact'] for r in rows),'/',len(rows),'NOISE_ACCEPT',sum(negative),flush=True)
