import numpy as np
from scipy.signal import correlate,find_peaks

import numpy as np
from scipy.signal import correlate,find_peaks
FS=2560000
rng=np.random.default_rng(9011)
pn=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,1024))).astype(np.complex64)
train=np.tile(pn,2)
tail=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,2048))).astype(np.complex64)
def recover_1(y):
    # CFO from repeating public training; same reference for every class.
    c=correlate(y,train,mode='valid',method='fft')
    peaks,_=find_peaks(np.abs(c),distance=5120)
    peaks=sorted(peaks,key=lambda p:abs(c[p]),reverse=True)
    for s in peaks:
        if s+5120>len(y):continue
        u=y[s:s+1024];v=y[s+1024:s+2048]
        f=np.angle(np.vdot(u-u.mean(),v-v.mean()))*FS/(2*np.pi*1024)
        n=np.arange(5120);z=y[s:s+5120]*np.exp(-2j*np.pi*f*n/FS)
        # Train on head public reference; tail checks calibration transfer.
        h=np.column_stack([train,np.ones(2048)])
        a,b=np.linalg.lstsq(h,z[:2048],rcond=None)[0]
        residual=np.sqrt(np.mean(abs(z[:2048]-h@np.array([a,b]))**2))/max(abs(a),1e-9)
        if abs(a)<.1:continue
        # Tail pilot at 3072; re-estimate gain and DC to interpolate drift.
        ht=np.column_stack([tail,np.ones(2048)])
        at,bt=np.linalg.lstsq(ht,z[3072:5120],rcond=None)[0]
        tail_residual=np.sqrt(np.mean(abs(z[3072:]-ht@np.array([at,bt]))**2))/max(abs(at),1e-9)
        ix=np.arange(2048,3072);w=(ix-1023.5)/3072
        aa=a*(1-w)+at*w;bb=b*(1-w)+bt*w
        # Public-reference FIR corrects fractional timing and passband response.
        lags=np.arange(-8,9)
        dc_basis=np.exp(-2j*np.pi*f*n/FS)
        design=np.column_stack([np.roll(train,k) for k in lags]+[dc_basis[:2048]])
        coef=np.linalg.lstsq(design[16:-16],z[16:2032],rcond=None)[0]
        head_error=np.linalg.norm(z[16:2032]-design[16:-16]@coef)/max(np.linalg.norm(z[16:2032]-z[16:2032].mean()),1e-9)
        if head_error>.2:continue
        tail_design=np.column_stack([np.roll(tail,k) for k in lags])
        predicted_tail=tail_design@coef[:-1]
        tail_fit=np.linalg.lstsq(np.column_stack([predicted_tail,dc_basis[3072:]])[16:-16],
                                 z[3088:5104],rcond=None)[0]
        tail_error=np.linalg.norm(z[3088:5104]-(predicted_tail*tail_fit[0]+tail_fit[1]*dc_basis[3072:])[16:-16])/max(np.linalg.norm(z[3088:5104]-z[3088:5104].mean()),1e-9)
        if tail_error>.2:continue
        drift=1*(1-w)+tail_fit[0]*w
        # Fit TX-LO leakage (constant after CFO correction) and RX DC
        # (rotating after CFO correction) using public head/tail only.
        indices=np.r_[np.arange(16,2032),np.arange(3088,5104)]
        public_signal=np.vstack([np.column_stack([np.roll(train,k) for k in lags])[16:-16],tail_design[16:-16]])
        public_weight=(indices-1023.5)/3072
        public_drift=1*(1-public_weight)+tail_fit[0]*public_weight
        public_design=np.column_stack([public_signal*public_drift[:,None],np.ones(len(indices)),dc_basis[indices]])
        joint=np.linalg.lstsq(public_design,z[indices],rcond=None)[0]
        offset=joint[-2]+joint[-1]*dc_basis[2048:3072]
        payload=((z[2048:3072]-offset)/drift).reshape(1,1024)
        omega=2*np.pi*np.fft.fftfreq(1024)
        response=np.exp(-1j*omega[:,None]*lags)@joint[:-2]
        inv=np.conj(response)/(abs(response)**2+1e-4*np.max(abs(response)**2))
        x=np.fft.ifft(np.fft.fft(payload,axis=1)*inv,axis=1)
        return x.reshape(1,1024),{'cfo_hz':float(f),'training_residual':float(residual),
          'fir_training_residual':float(np.linalg.norm(z[16:2032]-design[16:-16]@coef)/np.sqrt(2016)/abs(a)),
          'head_reference_relative_error':float(head_error),'tail_reference_relative_error':float(tail_error),
          'tail_residual':float(tail_residual),
          'gain':float(abs(a)),'dc':float(abs(b))}
    raise RuntimeError('no usable public preamble')

import numpy as np
from scipy.signal import correlate,find_peaks
FS=2560000
rng=np.random.default_rng(9011)
pn=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,1024))).astype(np.complex64)
train=np.tile(pn,2)
tail=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,2048))).astype(np.complex64)
def recover_2(y):
    # CFO from repeating public training; same reference for every class.
    c=correlate(y,train,mode='valid',method='fft')
    peaks,_=find_peaks(np.abs(c),distance=6144)
    peaks=sorted(peaks,key=lambda p:abs(c[p]),reverse=True)
    for s in peaks:
        if s+6144>len(y):continue
        u=y[s:s+1024];v=y[s+1024:s+2048]
        f=np.angle(np.vdot(u-u.mean(),v-v.mean()))*FS/(2*np.pi*1024)
        n=np.arange(6144);z=y[s:s+6144]*np.exp(-2j*np.pi*f*n/FS)
        # Train on head public reference; tail checks calibration transfer.
        h=np.column_stack([train,np.ones(2048)])
        a,b=np.linalg.lstsq(h,z[:2048],rcond=None)[0]
        residual=np.sqrt(np.mean(abs(z[:2048]-h@np.array([a,b]))**2))/max(abs(a),1e-9)
        if abs(a)<.1:continue
        # Tail pilot at 4096; re-estimate gain and DC to interpolate drift.
        ht=np.column_stack([tail,np.ones(2048)])
        at,bt=np.linalg.lstsq(ht,z[4096:6144],rcond=None)[0]
        tail_residual=np.sqrt(np.mean(abs(z[4096:]-ht@np.array([at,bt]))**2))/max(abs(at),1e-9)
        ix=np.arange(2048,4096);w=(ix-1023.5)/4096
        aa=a*(1-w)+at*w;bb=b*(1-w)+bt*w
        # Public-reference FIR corrects fractional timing and passband response.
        lags=np.arange(-8,9)
        dc_basis=np.exp(-2j*np.pi*f*n/FS)
        design=np.column_stack([np.roll(train,k) for k in lags]+[dc_basis[:2048]])
        coef=np.linalg.lstsq(design[16:-16],z[16:2032],rcond=None)[0]
        head_error=np.linalg.norm(z[16:2032]-design[16:-16]@coef)/max(np.linalg.norm(z[16:2032]-z[16:2032].mean()),1e-9)
        if head_error>.2:continue
        tail_design=np.column_stack([np.roll(tail,k) for k in lags])
        predicted_tail=tail_design@coef[:-1]
        tail_fit=np.linalg.lstsq(np.column_stack([predicted_tail,dc_basis[4096:]])[16:-16],
                                 z[4112:6128],rcond=None)[0]
        tail_error=np.linalg.norm(z[4112:6128]-(predicted_tail*tail_fit[0]+tail_fit[1]*dc_basis[4096:])[16:-16])/max(np.linalg.norm(z[4112:6128]-z[4112:6128].mean()),1e-9)
        if tail_error>.2:continue
        drift=1*(1-w)+tail_fit[0]*w
        # Fit TX-LO leakage (constant after CFO correction) and RX DC
        # (rotating after CFO correction) using public head/tail only.
        indices=np.r_[np.arange(16,2032),np.arange(4112,6128)]
        public_signal=np.vstack([np.column_stack([np.roll(train,k) for k in lags])[16:-16],tail_design[16:-16]])
        public_weight=(indices-1023.5)/4096
        public_drift=1*(1-public_weight)+tail_fit[0]*public_weight
        public_design=np.column_stack([public_signal*public_drift[:,None],np.ones(len(indices)),dc_basis[indices]])
        joint=np.linalg.lstsq(public_design,z[indices],rcond=None)[0]
        offset=joint[-2]+joint[-1]*dc_basis[2048:4096]
        payload=((z[2048:4096]-offset)/drift).reshape(2,1024)
        omega=2*np.pi*np.fft.fftfreq(1024)
        response=np.exp(-1j*omega[:,None]*lags)@joint[:-2]
        inv=np.conj(response)/(abs(response)**2+1e-4*np.max(abs(response)**2))
        x=np.fft.ifft(np.fft.fft(payload,axis=1)*inv,axis=1)
        return x.reshape(2,1024),{'cfo_hz':float(f),'training_residual':float(residual),
          'fir_training_residual':float(np.linalg.norm(z[16:2032]-design[16:-16]@coef)/np.sqrt(2016)/abs(a)),
          'head_reference_relative_error':float(head_error),'tail_reference_relative_error':float(tail_error),
          'tail_residual':float(tail_residual),
          'gain':float(abs(a)),'dc':float(abs(b))}
    raise RuntimeError('no usable public preamble')

import numpy as np
from scipy.signal import correlate,find_peaks
FS=2560000
rng=np.random.default_rng(9011)
pn=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,1024))).astype(np.complex64)
train=np.tile(pn,2)
tail=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,2048))).astype(np.complex64)
def recover_4(y):
    # CFO from repeating public training; same reference for every class.
    c=correlate(y,train,mode='valid',method='fft')
    peaks,_=find_peaks(np.abs(c),distance=8192)
    peaks=sorted(peaks,key=lambda p:abs(c[p]),reverse=True)
    for s in peaks:
        if s+8192>len(y):continue
        u=y[s:s+1024];v=y[s+1024:s+2048]
        f=np.angle(np.vdot(u-u.mean(),v-v.mean()))*FS/(2*np.pi*1024)
        n=np.arange(8192);z=y[s:s+8192]*np.exp(-2j*np.pi*f*n/FS)
        # Train on head public reference; tail checks calibration transfer.
        h=np.column_stack([train,np.ones(2048)])
        a,b=np.linalg.lstsq(h,z[:2048],rcond=None)[0]
        residual=np.sqrt(np.mean(abs(z[:2048]-h@np.array([a,b]))**2))/max(abs(a),1e-9)
        if abs(a)<.1:continue
        # Tail pilot at 6144; re-estimate gain and DC to interpolate drift.
        ht=np.column_stack([tail,np.ones(2048)])
        at,bt=np.linalg.lstsq(ht,z[6144:8192],rcond=None)[0]
        tail_residual=np.sqrt(np.mean(abs(z[6144:]-ht@np.array([at,bt]))**2))/max(abs(at),1e-9)
        ix=np.arange(2048,6144);w=(ix-1023.5)/6144
        aa=a*(1-w)+at*w;bb=b*(1-w)+bt*w
        # Public-reference FIR corrects fractional timing and passband response.
        lags=np.arange(-8,9)
        dc_basis=np.exp(-2j*np.pi*f*n/FS)
        design=np.column_stack([np.roll(train,k) for k in lags]+[dc_basis[:2048]])
        coef=np.linalg.lstsq(design[16:-16],z[16:2032],rcond=None)[0]
        head_error=np.linalg.norm(z[16:2032]-design[16:-16]@coef)/max(np.linalg.norm(z[16:2032]-z[16:2032].mean()),1e-9)
        if head_error>.2:continue
        tail_design=np.column_stack([np.roll(tail,k) for k in lags])
        predicted_tail=tail_design@coef[:-1]
        tail_fit=np.linalg.lstsq(np.column_stack([predicted_tail,dc_basis[6144:]])[16:-16],
                                 z[6160:8176],rcond=None)[0]
        tail_error=np.linalg.norm(z[6160:8176]-(predicted_tail*tail_fit[0]+tail_fit[1]*dc_basis[6144:])[16:-16])/max(np.linalg.norm(z[6160:8176]-z[6160:8176].mean()),1e-9)
        if tail_error>.2:continue
        drift=1*(1-w)+tail_fit[0]*w
        # Fit TX-LO leakage (constant after CFO correction) and RX DC
        # (rotating after CFO correction) using public head/tail only.
        indices=np.r_[np.arange(16,2032),np.arange(6160,8176)]
        public_signal=np.vstack([np.column_stack([np.roll(train,k) for k in lags])[16:-16],tail_design[16:-16]])
        public_weight=(indices-1023.5)/6144
        public_drift=1*(1-public_weight)+tail_fit[0]*public_weight
        public_design=np.column_stack([public_signal*public_drift[:,None],np.ones(len(indices)),dc_basis[indices]])
        joint=np.linalg.lstsq(public_design,z[indices],rcond=None)[0]
        offset=joint[-2]+joint[-1]*dc_basis[2048:6144]
        payload=((z[2048:6144]-offset)/drift).reshape(4,1024)
        omega=2*np.pi*np.fft.fftfreq(1024)
        response=np.exp(-1j*omega[:,None]*lags)@joint[:-2]
        inv=np.conj(response)/(abs(response)**2+1e-4*np.max(abs(response)**2))
        x=np.fft.ifft(np.fft.fft(payload,axis=1)*inv,axis=1)
        return x.reshape(4,1024),{'cfo_hz':float(f),'training_residual':float(residual),
          'fir_training_residual':float(np.linalg.norm(z[16:2032]-design[16:-16]@coef)/np.sqrt(2016)/abs(a)),
          'head_reference_relative_error':float(head_error),'tail_reference_relative_error':float(tail_error),
          'tail_residual':float(tail_residual),
          'gain':float(abs(a)),'dc':float(abs(b))}
    raise RuntimeError('no usable public preamble')

import numpy as np
from scipy.signal import correlate,find_peaks
FS=2560000
rng=np.random.default_rng(9011)
pn=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,1024))).astype(np.complex64)
train=np.tile(pn,2)
tail=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,2048))).astype(np.complex64)
def recover_8(y):
    # CFO from repeating public training; same reference for every class.
    c=correlate(y,train,mode='valid',method='fft')
    peaks,_=find_peaks(np.abs(c),distance=12288)
    peaks=sorted(peaks,key=lambda p:abs(c[p]),reverse=True)
    for s in peaks:
        if s+12288>len(y):continue
        u=y[s:s+1024];v=y[s+1024:s+2048]
        f=np.angle(np.vdot(u-u.mean(),v-v.mean()))*FS/(2*np.pi*1024)
        n=np.arange(12288);z=y[s:s+12288]*np.exp(-2j*np.pi*f*n/FS)
        # Train on head public reference; tail checks calibration transfer.
        h=np.column_stack([train,np.ones(2048)])
        a,b=np.linalg.lstsq(h,z[:2048],rcond=None)[0]
        residual=np.sqrt(np.mean(abs(z[:2048]-h@np.array([a,b]))**2))/max(abs(a),1e-9)
        if abs(a)<.1:continue
        # Tail pilot at 10240; re-estimate gain and DC to interpolate drift.
        ht=np.column_stack([tail,np.ones(2048)])
        at,bt=np.linalg.lstsq(ht,z[10240:12288],rcond=None)[0]
        tail_residual=np.sqrt(np.mean(abs(z[10240:]-ht@np.array([at,bt]))**2))/max(abs(at),1e-9)
        ix=np.arange(2048,10240);w=(ix-1023.5)/10240
        aa=a*(1-w)+at*w;bb=b*(1-w)+bt*w
        # Public-reference FIR corrects fractional timing and passband response.
        lags=np.arange(-8,9)
        dc_basis=np.exp(-2j*np.pi*f*n/FS)
        design=np.column_stack([np.roll(train,k) for k in lags]+[dc_basis[:2048]])
        coef=np.linalg.lstsq(design[16:-16],z[16:2032],rcond=None)[0]
        head_error=np.linalg.norm(z[16:2032]-design[16:-16]@coef)/max(np.linalg.norm(z[16:2032]-z[16:2032].mean()),1e-9)
        if head_error>.2:continue
        tail_design=np.column_stack([np.roll(tail,k) for k in lags])
        predicted_tail=tail_design@coef[:-1]
        tail_fit=np.linalg.lstsq(np.column_stack([predicted_tail,dc_basis[10240:]])[16:-16],
                                 z[10256:12272],rcond=None)[0]
        tail_error=np.linalg.norm(z[10256:12272]-(predicted_tail*tail_fit[0]+tail_fit[1]*dc_basis[10240:])[16:-16])/max(np.linalg.norm(z[10256:12272]-z[10256:12272].mean()),1e-9)
        if tail_error>.2:continue
        drift=1*(1-w)+tail_fit[0]*w
        # Fit TX-LO leakage (constant after CFO correction) and RX DC
        # (rotating after CFO correction) using public head/tail only.
        indices=np.r_[np.arange(16,2032),np.arange(10256,12272)]
        public_signal=np.vstack([np.column_stack([np.roll(train,k) for k in lags])[16:-16],tail_design[16:-16]])
        public_weight=(indices-1023.5)/10240
        public_drift=1*(1-public_weight)+tail_fit[0]*public_weight
        public_design=np.column_stack([public_signal*public_drift[:,None],np.ones(len(indices)),dc_basis[indices]])
        joint=np.linalg.lstsq(public_design,z[indices],rcond=None)[0]
        offset=joint[-2]+joint[-1]*dc_basis[2048:10240]
        payload=((z[2048:10240]-offset)/drift).reshape(8,1024)
        omega=2*np.pi*np.fft.fftfreq(1024)
        response=np.exp(-1j*omega[:,None]*lags)@joint[:-2]
        inv=np.conj(response)/(abs(response)**2+1e-4*np.max(abs(response)**2))
        x=np.fft.ifft(np.fft.fft(payload,axis=1)*inv,axis=1)
        return x.reshape(8,1024),{'cfo_hz':float(f),'training_residual':float(residual),
          'fir_training_residual':float(np.linalg.norm(z[16:2032]-design[16:-16]@coef)/np.sqrt(2016)/abs(a)),
          'head_reference_relative_error':float(head_error),'tail_reference_relative_error':float(tail_error),
          'tail_residual':float(tail_residual),
          'gain':float(abs(a)),'dc':float(abs(b))}
    raise RuntimeError('no usable public preamble')

def recover_auto(y):
 candidates=[]
 for count,fn in [(1,recover_1),(2,recover_2),(4,recover_4),(8,recover_8)]:
  try:
   x,meta=fn(y);candidates.append((meta['tail_reference_relative_error'],count,x,meta))
  except RuntimeError:pass
 if not candidates:raise RuntimeError('no supported public tail position')
 score,count,x,meta=min(candidates,key=lambda x:x[0]);meta=dict(meta,detected_repeats=float(count));return x,meta
