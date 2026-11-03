import sys,json,time,hashlib
from pathlib import Path
r=Path(r'E:\rml24_three_modes_execution_20261029');sys.path.insert(0,r'E:\scan_exec_20261027');from ui_interactive_tx import build_frame
sys.path.insert(0,r'E:\AMR_Rescue_20261025');import pluto_link_probe as link;import pilot_recovery as public
p=r.parent/'\u5d4c\u8d5b'/'rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset/03_02.bin';data=p.read_bytes();assert hashlib.sha256(data).hexdigest()=='1562575bbedd6e815535726f16de6752da0f7441ea609acd3cb2cf6be529c0f8'
uris=link.scan_usb();assert len(uris)==1,uris;radio=link.Radio(uris[0]);buffer=None
try:
 for ch,key,value in [(radio.tx,'hardwaregain',-40),(radio.tx,'sampling_frequency',2560000),(radio.tx,'rf_bandwidth',18000000),(radio.tlo,'frequency',2400000000),(radio.tlo,'powerdown',0)]:radio.set(ch,key,value)
 events=[]
 for name,active,seconds in [('signal_before',True,60),('muted',False,35),('signal_after',True,60)]:
  if active:buffer=radio.send(build_frame(data,public.train,public.tail))
  event=dict(phase=name,start_ns=time.time_ns(),active=active,seconds=seconds);events.append(event);(r/'reacquire01_events_private.json').write_text(json.dumps(events,indent=2));print('PHASE_STARTED',event,flush=True)
  time.sleep(seconds)
  if buffer is not None:radio.stop(buffer);buffer=None
  event['end_ns']=time.time_ns();(r/'reacquire01_events_private.json').write_text(json.dumps(events,indent=2))
finally:
 if buffer is not None:radio.stop(buffer)
 errors=radio.close();(r/'reacquire01_restore.json').write_text(json.dumps(errors));print('SINGLE_TX_STOPPED',time.time_ns(),errors,flush=True)
