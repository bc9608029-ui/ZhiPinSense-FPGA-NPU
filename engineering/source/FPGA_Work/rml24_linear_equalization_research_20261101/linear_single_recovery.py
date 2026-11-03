import numpy as np
from scipy.signal import correlate,find_peaks
FS=2560000
from adaptive_repeat_recovery import train,tail
def recover_linear(y):
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
        full_w=(n-1023.5)/3072
        full_drift=1*(1-full_w)+tail_fit[0]*full_w
        signal=(z-joint[-2]-joint[-1]*dc_basis)/full_drift
        omega=2*np.pi*np.fft.fftfreq(len(signal))
        response=np.exp(-1j*omega[:,None]*lags)@joint[:-2]
        inv=np.conj(response)/(abs(response)**2+1e-4*np.max(abs(response)**2))
        all_x=np.fft.ifft(np.fft.fft(signal)*inv)
        x=all_x[2048:3072].reshape(1,1024)
        return x.reshape(1,1024),{'cfo_hz':float(f),'training_residual':float(residual),
          'fir_training_residual':float(np.linalg.norm(z[16:2032]-design[16:-16]@coef)/np.sqrt(2016)/abs(a)),
          'head_reference_relative_error':float(head_error),'tail_reference_relative_error':float(tail_error),
          'tail_residual':float(tail_residual),
          'gain':float(abs(a)),'dc':float(abs(b))}
    raise RuntimeError('no usable public preamble')
