import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import sys,json,numpy as np
from pathlib import Path
p=Path(__file__).parent;sys.path.insert(0,str(p));sys.path.insert(0,'E:/FPGA_Work/rml24_repeat_agc_experiment_20261101')
from locked_detector import detect_locked
from adaptive_repeat_recovery import train,tail
from experimental_frame import build_frame
rng=np.random.default_rng(808123);x=np.exp(1j*np.pi/2*rng.integers(0,4,1024));payload=np.stack([x.real,x.imag]).astype('<f4').tobytes();frame=build_frame(payload,train,tail,8);rows=[]
for cfo in (-500000,-2000,-500,0,500,2000,500000):
 raw=np.roll(np.tile(frame,4),1739)*np.exp(2j*np.pi*cfo*np.arange(65536)/2560000)+.1*(rng.normal(size=65536)+1j*rng.normal(size=65536));d=detect_locked(raw,train);accepted=d['score']>=.1 and abs(d['coarse_cfo_hz'])<=1000;rows.append(dict(cfo=cfo,accepted=accepted,detection=d));print(cfo,accepted,d['score'],flush=True)
noise=[]
for i in range(24):
 raw=rng.normal(size=65536)+1j*rng.normal(size=65536);d=detect_locked(raw,train);noise.append(dict(index=i,accepted=d['score']>=.1 and abs(d['coarse_cfo_hz'])<=1000,detection=d))
(p/'LOCKED_SCOPE_TEST.json').write_text(json.dumps(dict(scope='PC synthetic development; not RF qualification; only centered-lock use',cfo_cases=rows,noise_cases=noise,false_noise_accepts=sum(x['accepted'] for x in noise)),indent=2));print('NOISE_ACCEPTED',sum(x['accepted'] for x in noise),flush=True)
