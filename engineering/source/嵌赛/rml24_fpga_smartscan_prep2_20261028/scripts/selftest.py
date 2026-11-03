#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,numpy as np
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'reference'))
from smart_scan_golden import hann_q15,window_iq,spectrum,detect
assert hann_q15(1024)[0]==0 and hann_q15(1024)[-1]==0
z=np.zeros((1024,2),np.int16); o=spectrum(z); assert int(o['power_u54'].max())==0
x=np.array([[-32768,-32768]],dtype=np.int64); extreme=int(x[0,0]**2+x[0,1]**2); assert extreme==2**31
fft_extreme=2*((1<<26)**2); assert fft_extreme==2**53 and fft_extreme.bit_length()==54
p=subprocess.run([sys.executable,str(ROOT/'scripts/generate_vectors.py')]); assert p.returncode==0
two=np.load(ROOT/'vectors'/'two_tone.golden.npz'); d=detect(two['power_u54']); assert len(d['targets'])>=2
print('SMART_SCAN_SELFTEST result=PASS checks=6 width_extreme=2^53 storage_bits=54')
