import numpy as np
from scipy.signal import correlate,find_peaks
FS=2560000
rng=np.random.default_rng(9011)
pn=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,1024))).astype(np.complex64)
train=np.tile(pn,2)
tail=np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,2048))).astype(np.complex64)
def recover(y):
    # CFO from repeating public training; same reference for every class.
    c=correlate(y,train,mode='valid',method='fft')
    peaks,_=find_peaks(np.abs(c),distance=14000)
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
        offset=(coef[-1]*(1-w)+tail_fit[1]*w)*dc_basis[2048:10240]
        tail_full=np.column_stack([np.roll(tail,k) for k in lags]+[dc_basis[10240:]])
        tail_coef=np.linalg.lstsq(tail_full[16:-16],z[10256:12272],rcond=None)[0]
        offset=(coef[-1]*(1-w)+tail_coef[-1]*w)*dc_basis[2048:10240]
        payload=(z[2048:10240]-offset).reshape(8,1024)
        omega=2*np.pi*np.fft.fftfreq(1024)
        blend=w.reshape(8,1024).mean(axis=1)
        interpolated=coef[:-1][None,:]*(1-blend[:,None])+tail_coef[:-1][None,:]*blend[:,None]
        response=(np.exp(-1j*omega[:,None]*lags)@interpolated.T).T
        inv=np.conj(response)/(abs(response)**2+1e-4*np.max(abs(response)**2,axis=1,keepdims=True))
        x=np.fft.ifft(np.fft.fft(payload,axis=1)*inv,axis=1)
        return x.reshape(8,1024),{'cfo_hz':float(f),'training_residual':float(residual),
          'fir_training_residual':float(np.linalg.norm(z[16:2032]-design[16:-16]@coef)/np.sqrt(2016)/abs(a)),
          'head_reference_relative_error':float(head_error),'tail_reference_relative_error':float(tail_error),
          'tail_residual':float(tail_residual),
          'gain':float(abs(a)),'dc':float(abs(b))}
    raise RuntimeError('no usable public preamble')
