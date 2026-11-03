class GainFreeze:
 """Prototype, callback IO only. Caller retains original radio snapshot once."""
 def __init__(self,read,write,prime):self.read=read;self.write=write;self.prime=prime
 def prepare_capture(self):
  old_mode=self.read('gain_control_mode');old_gain=float(self.read('hardwaregain').split()[0])
  try:
   self.write('gain_control_mode','slow_attack')
   for _ in range(3):self.prime()
   gain=float(self.read('hardwaregain').split()[0])
   if not -3<=gain<=71:raise RuntimeError('RX gain readback outside hardware range')
   self.write('gain_control_mode','manual');self.write('hardwaregain',gain)
   actual=float(self.read('hardwaregain').split()[0])
   if abs(actual-gain)>1:raise RuntimeError('freeze gain readback mismatch')
   if self.read('gain_control_mode')!='manual':raise RuntimeError('gain mode not frozen')
   return dict(selected_gain_db=gain,readback_gain_db=actual,settle_buffers=3)
  except Exception:
   self.write('gain_control_mode','manual');self.write('hardwaregain',old_gain)
   if old_mode!='manual':self.write('gain_control_mode',old_mode)
   raise
