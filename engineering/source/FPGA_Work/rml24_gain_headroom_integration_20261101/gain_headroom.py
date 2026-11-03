import math,numpy as np

def adc_stats(raw):
 z=np.asarray(raw)
 if z.ndim!=1 or not np.iscomplexobj(z) or not np.isfinite(z).all():raise RuntimeError('invalid RX IQ')
 c=np.r_[z.real,z.imag];return dict(peak=float(abs(c).max()),rail_count=int(np.sum((c==-2048)|(c==2047))))

class GainHeadroom:
 def __init__(self,freeze,read,write,capture):self.freeze=freeze;self.read=read;self.write=write;self.capture=capture
 def receive(self,n):
  metadata=self.freeze.prepare_capture();raw=self.capture(n);s=adc_stats(raw);first=dict(s);gain=metadata['readback_gain_db'];low=float(self.read('hardwaregain_available').strip('[]').split()[0]);steps=[]
  for _ in range(3):
   if s['peak']<.9*2048:break
   backoff=6 if s['rail_count'] else max(1,math.ceil(20*math.log10(s['peak']/(.8*2048))));requested=max(low,gain-backoff)
   if requested>=gain:break
   self.write('hardwaregain',requested);actual=float(self.read('hardwaregain').split()[0])
   if abs(actual-requested)>1 or self.read('gain_control_mode')!='manual':raise RuntimeError('gain backoff readback mismatch')
   raw=self.capture(n);s=adc_stats(raw);steps.append(dict(before_gain=gain,requested=requested,readback=actual,stats=dict(s)));gain=actual
  return raw,dict(metadata,initial_adc_stats=first,final_adc_stats=s,final_gain_db=gain,backoff_steps=steps,headroom_resolved=s['rail_count']==0)
