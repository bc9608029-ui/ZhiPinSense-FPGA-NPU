"""Independent scheduled PC transmitter; no socket/control channel to RX."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,time,json,os
import numpy as np
from common import ROOT,read,sha,load,IDENTITY

def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True);p.add_argument('--tx-uri')
 p.add_argument('--libiio-library',type=Path,help='explicit libiio 0.x DLL; Windows requires its dependency directory')
 p.add_argument('--transmit',action='store_true');a=p.parse_args()
 plan=read(a.plan);frames=[]
 builder=load('experiment_frame',ROOT/'tx/vendor/frame_builder.py')
 public=load('experiment_public',ROOT/'tx/vendor/pilot_recovery.py')
 for r in plan['rows']:
  path=ROOT/'tx/assets'/r['file']
  if path.resolve().parent!=(ROOT/'tx/assets').resolve() or sha(path)!=r['source_sha256']:raise ValueError('source identity')
  frames.append(builder.build_frame(path.read_bytes(),public.train,public.tail))
 a.out.mkdir(exist_ok=False);radio=None;buffer=None
 if not a.transmit:
  for i,frame in enumerate(frames):np.save(a.out/('%02d.frame.npy'%i),frame)
  print('DRY_RUN_ONLY no radio imported');return
 if not a.tx_uri:raise ValueError('explicit --tx-uri required')
 if time.time_ns()+5_000_000_000>=plan['start_ns']:raise ValueError('start must be >5s in future')
 dll_handles=[]
 if a.libiio_library:
  dll=a.libiio_library.resolve()
  if not dll.is_file():raise ValueError('libiio library not found')
  os.environ['LIBIIO_LIBRARY']=str(dll)
  if os.name=='nt':dll_handles.append(os.add_dll_directory(str(dll.parent)))
 link=load('experiment_radio',ROOT/'tx/vendor/pluto_link_probe.py',IDENTITY['radio'])
 original=[]
 try:
  radio=link.Radio(a.tx_uri)
  original=[(ch,key,radio.get(ch,key)) for ch,key in [(radio.tx,'hardwaregain'),(radio.tx,'sampling_frequency'),
             (radio.tx,'rf_bandwidth'),(radio.tlo,'frequency')]]
  for ch,key,val in [(radio.tx,'hardwaregain',-40),(radio.tx,'sampling_frequency',2560000),
                     (radio.tx,'rf_bandwidth',18000000),(radio.tlo,'frequency',2400000000)]:
   radio.set(ch,key,val)
   if abs(float(radio.get(ch,key).split()[0])-val)>.1:raise RuntimeError('TX readback '+key)
  with (a.out/'tx_events.jsonl').open('x',encoding='utf8') as log:
   for r,frame in zip(plan['rows'],frames):
    while time.time_ns()<r['start_ns']:time.sleep(.01)
    if time.time_ns()-r['start_ns']>250_000_000:raise RuntimeError('TX schedule late; stop and invalidate')
    buffer=radio.send(frame);begin=time.time_ns()
    while time.time_ns()<r['end_ns']:time.sleep(.01)
    end=time.time_ns();radio.stop(buffer);buffer=None
    log.write(json.dumps(dict(opportunity=r['opportunity'],start_ns=begin,end_ns=end,
                              plan_sha256=sha(a.plan)))+'\n');log.flush()
 finally:
  errors=[]
  if radio:
   try:
    if buffer is not None:radio.stop(buffer)
   finally:errors=radio.close() or []
  from common import write
  verified=False;values={};check=None
  if original:
   try:
    check=link.Radio(a.tx_uri);verified=not errors
    # Channel handles belong to the old context: resolve fresh TX/LO handles.
    for i,(_,key,expected) in enumerate(original):
     channel=check.tlo if i==3 else check.tx
     actual=check.get(channel,key);values[key]=actual
     verified=verified and abs(float(actual.split()[0])-float(expected.split()[0]))<.11
   finally:
    if check:check.close()
  write(a.out/'tx_restore.json',dict(write_restore_errors=errors,readback_verified=verified,readback=values))
  if errors or not verified:raise RuntimeError('TX restore readback failed')
 print('TX_FINISHED restore_readback=PASS')
if __name__=='__main__':main()
