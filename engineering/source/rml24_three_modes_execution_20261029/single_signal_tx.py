import sys,json,time,hashlib
from pathlib import Path
r=Path(r'E:\rml24_three_modes_execution_20261029');sys.path.insert(0,r'E:\scan_exec_20261027');from ui_interactive_tx import build_frame
sys.path.insert(0,r'E:\AMR_Rescue_20261025');import pluto_link_probe as link;import pilot_recovery as public
p=r.parent/'\u5d4c\u8d5b'/'rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset/03_02.bin';data=p.read_bytes();assert hashlib.sha256(data).hexdigest()=='1562575bbedd6e815535726f16de6752da0f7441ea609acd3cb2cf6be529c0f8'
uris=link.scan_usb();assert len(uris)==1,uris;radio=link.Radio(uris[0]);buffer=None
try:
 for ch,key,value in [(radio.tx,'hardwaregain',-40),(radio.tx,'sampling_frequency',2560000),(radio.tx,'rf_bandwidth',18000000),(radio.tlo,'frequency',2400000000),(radio.tlo,'powerdown',0)]:radio.set(ch,key,value)
 buffer=radio.send(build_frame(data,public.train,public.tail));start=time.time_ns();print('SINGLE_TX_STARTED',start,flush=True);time.sleep(300)
finally:
 if buffer is not None:radio.stop(buffer)
 errors=radio.close();(r/'single_signal01_restore.json').write_text(json.dumps(errors));print('SINGLE_TX_STOPPED',time.time_ns(),errors,flush=True)
