#!/usr/bin/env python3
"""Float/fixed-boundary Golden for FPGA-assisted spectrum scanning."""
from __future__ import annotations
import numpy as np

def round_away(x):
    x=np.asarray(x,dtype=np.float64); return (np.sign(x)*np.floor(np.abs(x)+0.5)).astype(np.int64)

def hann_q15(n):
    if n<2: raise ValueError('n')
    return np.clip(round_away(np.hanning(n)*(1<<15)),-32768,32767).astype(np.int16)

def rshift_away(x,shift):
    x=np.asarray(x,dtype=np.int64); a=np.abs(x); y=(a+(1<<(shift-1)))>>shift
    return np.where(x<0,-y,y).astype(np.int64)

def window_iq(iq):
    x=np.asarray(iq); 
    if x.dtype!=np.int16 or x.ndim!=2 or x.shape[1]!=2: raise ValueError('int16 [N,2] required')
    w=hann_q15(len(x)).astype(np.int64)[:,None]; y=rshift_away(x.astype(np.int64)*w,15)
    return np.clip(y,-32768,32767).astype(np.int16)

def spectrum(iq,fs=2_560_000):
    y=window_iq(iq); z=y[:,0].astype(np.float64)+1j*y[:,1].astype(np.float64)
    X=np.fft.fftshift(np.fft.fft(z)); re=round_away(X.real); im=round_away(X.imag)
    limit=1<<26
    if np.any(re < -limit) or np.any(re >= limit) or np.any(im < -limit) or np.any(im >= limit):
        raise OverflowError('unscaled FFT exceeds signed-27 boundary')
    power=re*re+im*im
    freq=(np.arange(len(z))-len(z)//2)*fs/len(z)
    return {'windowed':y,'fft_re':re,'fft_im':im,'power_u54':power,'freq_hz':freq}

def detect(power,fs=2_560_000,guard_bins=3,threshold_db=10.0,min_bins=1):
    p=np.asarray(power,dtype=np.float64); n=len(p)
    # Robust global floor is V1 CPU policy; it is deliberately not claimed as CFAR.
    floor=float(np.median(p)); threshold=max(floor*10**(threshold_db/10),1.0)
    active=p>threshold; groups=[]; i=0
    while i<n:
        if not active[i]: i+=1; continue
        j=i
        while j+1<n and active[j+1]: j+=1
        if j-i+1>=min_bins:
            sl=slice(i,j+1); weights=p[sl]-floor; bins=np.arange(i,j+1)
            center=float(np.sum(bins*weights)/max(np.sum(weights),1e-30))
            groups.append({'first_bin':i,'last_bin':j,'peak_bin':int(i+np.argmax(p[sl])),
                           'center_offset_hz':(center-n/2)*fs/n,'bandwidth_hz':(j-i+1)*fs/n,
                           'peak_power':float(np.max(p[sl])),'noise_floor':floor})
        i=j+1
    return {'noise_floor':floor,'threshold':threshold,'targets':groups}
