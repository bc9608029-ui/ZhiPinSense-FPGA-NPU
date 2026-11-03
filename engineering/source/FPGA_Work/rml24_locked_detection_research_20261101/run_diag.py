import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,time,json,subprocess,re,base64,gzip
p=Path(__file__).parent
sys.path.insert(0,'E:/FPGA_Work/rml24_gainfreeze_formal_prep_20261101');from timing_contract import pc_monotonic_ns
sys.path.insert(0,'E:/FPGA_Work/rml24_range_expansion_20261101/pc/console/vendor');import pluto_link_probe as link;import pilot_recovery as public;from frame_builder import build_frame
serial='E:/scan_exec_20261027/serial.ps1'
def ps(argv):
 q=subprocess.run(['powershell','-NoProfile','-File']+argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);s=q.stdout.decode('utf8',errors='replace');assert q.returncode==0,s;return s
def board(cmd,seconds=3):return ps([serial,'-Command',cmd,'-Seconds',str(seconds)])
(p/'CLOCK_PRE.json').write_text(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']))
cmd='nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/capture_locked.py > /root/locked_diag_20261101.log 2>&1 < /dev/null &'
(p/'START.txt').write_text(board(cmd));radio=None;buffer=None;events=[]
try:
 time.sleep(8)
 t=board('test -f /root/rml24_locked_detection_research_20261101/PROGRESS.json && echo DIAG_READY; tail -c 600 /root/locked_diag_20261101.log')
 (p/'READY.txt').write_text(t);assert re.search(r'(?:^|[\r\n])DIAG_READY',t),t
 uris=link.scan_usb();assert len(uris)==1;radio=link.Radio(uris[0])
 for role,key,value in [('tx','hardwaregain',-40),('tx','sampling_frequency',2560000),('tx','rf_bandwidth',18000000),('tlo','frequency',2403600000),('tlo','powerdown',0)]:radio.set(getattr(radio,role),key,value)
 assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets')
 for name in ('14_05.bin','13_01.bin','17_00.bin','18_06.bin','18_07.bin','23_04.bin'):
  buffer=radio.send(build_frame((assets/name).read_bytes(),public.train,public.tail));begin=pc_monotonic_ns();time.sleep(9);radio.stop(buffer);buffer=None;events.append(dict(file=name,start_mono_ns=begin,end_mono_ns=pc_monotonic_ns()));(p/'PRIVATE_EVENTS.json').write_text(json.dumps(events,indent=2));print('TX_DONE',name,flush=True);time.sleep(.5)
finally:
 if radio is not None:
  if buffer is not None:radio.stop(buffer)
  errors=radio.close();(p/'TX_RESTORE.json').write_text(json.dumps(dict(errors=errors)));assert not errors
for _ in range(30):
 t=board('test -f /root/rml24_locked_detection_research_20261101/RESULT.json && echo DIAG_FINISHED; tail -c 300 /root/locked_diag_20261101.log',2)
 if re.search(r'(?:^|[\r\n])DIAG_FINISHED',t):break
 time.sleep(4)
else:raise RuntimeError('capture result absent; inspect device log')
(p/'FINISH.txt').write_text(t)
(p/'CLOCK_POST.json').write_text(ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']))
cmd='python3 -c \'import pathlib,base64,gzip; p=pathlib.Path("/root/rml24_locked_detection_research_20261101/RESULT.json"); print("DIAG_BEGIN"+base64.b64encode(gzip.compress(p.read_bytes())).decode()+"DIAG_END")\''
t=board(cmd,5);(p/'EXPORT.txt').write_text(t);m=re.search(r'(?:^|[\r\n])DIAG_BEGIN([A-Za-z0-9+/=\s]+)DIAG_END',t);assert m;v=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',m[1]))));(p/'RESULT.json').write_text(json.dumps(v,indent=2));assert v['restore_errors']==[];print('SHORT_DIAGNOSTIC_CAPTURE_COMPLETE_NOT_DEPLOYED',len(v['rows']),flush=True)
