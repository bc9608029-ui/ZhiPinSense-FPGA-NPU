"""Independent display PSD backend. Never modifies inference tensor or detector."""
import json,subprocess,tempfile,time
from pathlib import Path
import numpy as np
class UnsafeHardware(RuntimeError): pass
class SpectrumBackend:
 def __init__(self,mode='software',driver=None,evidence=None):
  if mode not in ('software','fpga','auto'):raise ValueError('mode')
  if mode!='software' and not driver:raise ValueError('explicit driver required')
  self.mode=mode;self.driver=driver;self.evidence=Path(evidence) if evidence else None;self.last_backend='software';self.count=0;self.rpc=None
 def __call__(self,z):
  z=np.asarray(z,dtype=np.complex128)
  if z.shape!=(1024,) or not np.isfinite(z).all():raise ValueError('invalid display IQ')
  tick=time.monotonic();reason=None;used='software';peak=max(float(np.max(np.abs(z.real))),float(np.max(np.abs(z.imag))))
  if self.mode=='software' or peak==0:
   power=np.abs(np.fft.fftshift(np.fft.fft(z*np.hanning(1024))))**2
  else:
   scale=16384.0/peak;x=np.column_stack((z.real,z.imag))*scale;q=np.rint(x)
   if np.any(q>32767) or np.any(q< -32768):raise ValueError('unexpected quantizer clipping')
   if self.rpc is not None:
    a=np.asarray(self.rpc(q.astype('<i2')))
    if a.shape!=(1024,) or a.dtype!=np.dtype('<u8') or np.any(a>>54):raise ValueError('invalid shared PSD')
    power=a.astype(np.float64)/(scale*scale);used='fpga'
   else:
    with tempfile.TemporaryDirectory(prefix='rml24_display_psd_') as folder:
     p=Path(folder);q.astype('<i2').tofile(p/'iq.i16')
     try:
      # No external timeout/kill: the DDR-owning driver enforces its own deadline.
      run=subprocess.run([self.driver,'--execute',str(p/'iq.i16'),str(p/'power.u64'),str(p/'driver.json')],capture_output=True,text=True)
     except OSError as exc:
      if self.mode!='auto':raise
      reason='driver_launch_failed:'+str(exc);run=None
     if run is not None:
      if run.returncode==3:raise UnsafeHardware('UNSAFE_BUSY_REQUIRES_BOARD_RESET '+run.stderr)
      if run.returncode:raise RuntimeError('driver failed; no silent fallback: '+run.stdout+run.stderr)
      a=np.fromfile(p/'power.u64',dtype='<u8')
      if a.shape!=(1024,) or np.any(a>>54):raise ValueError('invalid PSD output')
      power=a.astype(np.float64)/(scale*scale);used='fpga'
     else:power=np.abs(np.fft.fftshift(np.fft.fft(z*np.hanning(1024))))**2
  self.last_backend=used;self.count+=1
  if self.evidence:
   with self.evidence.open('a') as f:f.write(json.dumps(dict(frame=self.count,requested=self.mode,backend_used=used,fallback_reason=reason,latency_us=(time.monotonic()-tick)*1e6,normalization='label_blind_peak_to_16384_display_only',zero_input=peak==0))+'\n')
  return power
