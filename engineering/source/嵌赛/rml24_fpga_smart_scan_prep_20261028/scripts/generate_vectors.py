#!/usr/bin/env python3
from pathlib import Path
import json,sys,numpy as np
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'reference'))
from smart_scan_golden import spectrum,detect

def make(freqs,amps,seed):
    n=1024; fs=2_560_000; t=np.arange(n)/fs; rng=np.random.default_rng(seed)
    z=sum(a*np.exp(2j*np.pi*f*t) for f,a in zip(freqs,amps))+0.015*(rng.normal(size=n)+1j*rng.normal(size=n))
    z=np.clip(z.real,-.999,.999)+1j*np.clip(z.imag,-.999,.999)
    return np.column_stack((np.rint(z.real*32767),np.rint(z.imag*32767))).astype('<i2')

cases=[('zero',[],[],1),('one_tone',[200_000],[.7],2),('two_tone',[-400_000,350_000],[.8,.3],3),('edge',[1_200_000],[.5],4)]
manifest=[]
for name,f,a,seed in cases:
    iq=make(f,a,seed); out=spectrum(iq); det=detect(out['power_u52'])
    iq.tofile(ROOT/'vectors'/f'{name}.iq.i16'); np.savez_compressed(ROOT/'vectors'/f'{name}.golden.npz',**out)
    manifest.append({'name':name,'tones_hz':f,'amplitudes':a,'seed':seed,'targets':det['targets']})
(ROOT/'vectors'/'manifest.json').write_text(json.dumps({'fs_hz':2560000,'fft_length':1024,'cases':manifest},indent=2)+'\n',encoding='utf-8')
print('VECTOR_GENERATION result=PASS cases=4')
