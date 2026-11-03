class GainFreeze:
 """Prototype, callback IO only. Caller retains original radio snapshot once."""
 def __init__(self,read,write,prime):self.read=read;self.write=write;self.prime=prime
 def prepare_capture(self):
  old_mode=self.read('gain_control_mode');old_gain=float(self.read('hardwaregain').split()[0])
  try:
   self.write('gain_control_mode','slow_attack')
   for _ in range(3):self.prime()
   gain=float(self.read('hardwaregain').split()[0])
   bounds=self.read('hardwaregain_available').strip('[]').split();low,high=float(bounds[0]),float(bounds[-1])
   if not low<=gain<=high:raise RuntimeError('RX gain readback outside current hardware range')
   self.write('gain_control_mode','manual');self.write('hardwaregain',gain)
   actual=float(self.read('hardwaregain').split()[0])
   if abs(actual-gain)>1:raise RuntimeError('freeze gain readback mismatch')
   if self.read('gain_control_mode')!='manual':raise RuntimeError('gain mode not frozen')
   return dict(selected_gain_db=gain,readback_gain_db=actual,settle_buffers=3)
  except Exception:
   self.write('gain_control_mode','manual');self.write('hardwaregain',old_gain)
   if old_mode!='manual':self.write('gain_control_mode',old_mode)
   raise

def install(legacy_root):
 import sys
 sys.path.insert(0,str(legacy_root));import pluto_link_probe as link
 cls=link.Radio
 if getattr(cls,'_gainfreeze_installed',False):return
 original_config=cls.config_rx;original_receive=cls.receive
 def bounded_receive(self,n):
  try:return original_receive(self,n)
  finally:
   if hasattr(self,'enabled'):
    kept=[];seen=set()
    for ch,old in self.enabled:
     key=getattr(ch,'value',ch)
     if key not in seen:seen.add(key);kept.append((ch,old))
    self.enabled[:]=kept
 def config(self):
  original_config(self);self.set(self.rx,'rf_bandwidth',5000000)
  def read(key):return self.get(self.rx,key)
  def write(key,value):
   rc=link.writeattr(self.rx,key.encode(),str(value).encode())
   if rc<0:raise RuntimeError('gain control write rejected '+key+' '+str(rc))
  self._gainfreeze_controller=GainFreeze(read,write,lambda:bounded_receive(self,16384))
 def receive(self,n=65536):
  controller=getattr(self,'_gainfreeze_controller',None)
  if controller is not None:self.gain_freeze_last=controller.prepare_capture()
  return bounded_receive(self,n)
 cls.config_rx=config;cls.receive=receive;cls._gainfreeze_installed=True
