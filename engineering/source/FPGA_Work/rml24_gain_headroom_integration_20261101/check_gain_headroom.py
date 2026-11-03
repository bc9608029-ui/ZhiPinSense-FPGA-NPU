from pathlib import Path
import numpy as np,json
from gain_headroom import GainHeadroom
class Freeze:
 def __init__(self,io):self.io=io
 def prepare_capture(self):return dict(readback_gain_db=self.io.gain,selected_gain_db=self.io.gain,settle_buffers=3)
class IO:
 def __init__(self,gain=50,low=0,stuck=False):self.gain=gain;self.low=low;self.calls=0;self.writes=[];self.stuck=stuck
 def read(self,key):return str(self.gain) if key=='hardwaregain' else '[%s 1 71]'%self.low if key=='hardwaregain_available' else 'manual'
 def write(self,key,value):
  self.writes.append((key,value))
  if not self.stuck:self.gain=float(value)
 def capture(self,n):self.calls+=1;return self.sequence[min(self.calls-1,len(self.sequence)-1)]
low=np.full(16,500+100j,np.complex64);clipped=np.full(16,2047-2048j,np.complex64);rows=[]
io=IO();io.sequence=[low];raw,m=GainHeadroom(Freeze(io),io.read,io.write,io.capture).receive(16);assert raw is low and io.calls==1 and not io.writes;rows.append('safe_capture_identity_no_extra_io')
io=IO();io.sequence=[clipped,low];raw,m=GainHeadroom(Freeze(io),io.read,io.write,io.capture).receive(16);assert raw is low and io.gain==44 and io.calls==2 and m['headroom_resolved'];rows.append('saturation_backoff_reacquires')
io=IO(gain=3);io.sequence=[clipped];raw,m=GainHeadroom(Freeze(io),io.read,io.write,io.capture).receive(16);assert io.gain==0 and io.calls==2 and not m['headroom_resolved'];rows.append('native_minimum_never_exceeded')
io=IO();io.sequence=[clipped];raw,m=GainHeadroom(Freeze(io),io.read,io.write,io.capture).receive(16);assert io.calls==4 and len(m['backoff_steps'])==3;rows.append('bounded_reacquisition')
io=IO(stuck=True);io.sequence=[clipped]
try:GainHeadroom(Freeze(io),io.read,io.write,io.capture).receive(16);raise AssertionError('expected readback failure')
except RuntimeError:rows.append('hardware_write_readback_failure_propagates')
Path(__file__).with_name('SOFTWARE_CONTRACT_CHECK.json').write_text(json.dumps(dict(scope='Callback software contract only, not RF qualification',passed=rows),indent=2));print('GAIN_HEADROOM_SOFTWARE_PASS',len(rows))
