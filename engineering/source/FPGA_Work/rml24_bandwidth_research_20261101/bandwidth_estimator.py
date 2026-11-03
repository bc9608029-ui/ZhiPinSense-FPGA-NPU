import numpy as np
def estimate_bandwidth(iq,fs,energy_fraction=.99):
 z=np.asarray(iq,np.complex128)
 if z.ndim!=1 or len(z)<256 or not np.isfinite(z).all():raise ValueError('invalid IQ')
 z=z-z.mean();n=min(1024,len(z));segments=[z[i:i+n] for i in range(0,len(z)-n+1,n//2)];w=np.hanning(n);psd=np.mean([abs(np.fft.fftshift(np.fft.fft(x*w)))**2 for x in segments],axis=0);noise=float(np.median(psd));signal=np.maximum(psd-noise,0);total=float(signal.sum())
 if total<=1e-20:return dict(valid=False,reason='no excess energy')
 c=np.cumsum(signal)/total;lo=int(np.searchsorted(c,(1-energy_fraction)/2));hi=int(np.searchsorted(c,1-(1-energy_fraction)/2));freq=np.fft.fftshift(np.fft.fftfreq(n,1/fs));return dict(valid=True,low_hz=float(freq[lo]),high_hz=float(freq[min(hi,n-1)]),span_hz=float((hi-lo+1)*fs/n),touches_sample_band_edge=bool(lo<3 or hi>n-4),method='Welch-like PSD median-subtracted99percent energy; diagnostic heuristic')
