"""RX-only continuous capture. Accepts no TX plan, labels, source IQ or sockets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,time,json,shutil
import numpy as np
from common import load,IDENTITY,sha,write
from gain_tools.gain_control import configure

def main():
 p=argparse.ArgumentParser();p.add_argument('--radio',type=Path,required=True)
 p.add_argument('--rx-uri',required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--mode',choices=['manual','slow_attack'],required=True);p.add_argument('--gain',type=float)
 p.add_argument('--seconds',type=int,default=210);p.add_argument('--period-ms',type=int,default=1000)
 a=p.parse_args()
 if not 10<=a.seconds<=7200 or not 100<=a.period_ms<=2000:raise ValueError('duration/period bounds')
 estimate=int(a.seconds*1000/a.period_ms+1)*65536*8
 if shutil.disk_usage(a.out.parent).free<estimate+256*1024**2:raise RuntimeError('insufficient disk space')
 link=load('rx_experiment_radio',a.radio,IDENTITY['radio']);a.out.mkdir(exist_ok=False)
 radio=link.Radio(a.rx_uri);original={k:radio.get(radio.rx,k) for k in
 ['gain_control_mode','hardwaregain','sampling_frequency','rf_bandwidth']}
 original_lo=radio.get(radio.rlo,'frequency');count=0;errors=[];failure=None
 started=time.monotonic();wall=time.time_ns()
 try:
  radio.config_rx();applied=configure(radio,a.mode,a.gain)
  for _ in range(2):radio.receive(65536)
  with (a.out/'captures.jsonl').open('x') as log:
   while time.monotonic()-started<a.seconds:
    tick=time.monotonic();begin=time.time_ns();raw=radio.receive(65536);end=time.time_ns()
    if abs((end-wall)/1e9-(time.monotonic()-started))>.1:raise RuntimeError('RX wall clock jumped')
    if raw.shape!=(65536,) or not np.isfinite(raw).all():raise RuntimeError('invalid capture')
    f=a.out/('%06d.raw.npy'%count);np.save(f,raw)
    log.write(json.dumps(dict(record_id=count,capture_start_ns=begin,capture_end_ns=end,
                             file=f.name,sha256=sha(f),gain_db=radio.get(radio.rx,'hardwaregain')))+'\n');log.flush()
    count+=1;time.sleep(max(0,a.period_ms/1000-(time.monotonic()-tick)))
 except BaseException as e:failure=str(e);raise
 finally:
  try:errors=radio.close() or []
  finally:write(a.out/'capture_summary.json',dict(raw_records=count,error=failure,write_restore_errors=errors))
 check=link.Radio(a.rx_uri)
 try:
  readback={k:check.get(check.rx,k) for k in original};lo=check.get(check.rlo,'frequency')
  good=not errors and lo==original_lo
  for k,v in original.items():
   if k=='gain_control_mode':good=good and readback[k]==v
   elif k=='hardwaregain' and original['gain_control_mode']!='manual':continue
   else:good=good and abs(float(v.split()[0])-float(readback[k].split()[0]))<.11
 finally:check.close()
 write(a.out/'restore_readback.json',dict(restore_verified=good,readback=readback,lo=lo))
 if not good:raise RuntimeError('RX restore readback mismatch')
 print('RX_CAPTURE_COMPLETE',count,applied)
if __name__=='__main__':main()
