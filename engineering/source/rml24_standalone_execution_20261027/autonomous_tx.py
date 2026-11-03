"""Independent timed TX. Does not connect to or exchange messages with RX."""
import argparse,hashlib,importlib,json,sys,time
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser()
p.add_argument('--out',type=Path,required=True)
p.add_argument('--mode',choices=['smoke24','formal240'],default='smoke24')
p.add_argument('--center-hz',type=int,default=2400000000)
p.add_argument('--hold-sec',type=float,default=6)
p.add_argument('--mute-sec',type=float,default=8)
p.add_argument('--warmup-sec',type=float,default=0)
a=p.parse_args();a.out.mkdir(exist_ok=False,parents=True)
root=Path(__file__).parent
sys.path.insert(0,str(root.parent/'scan_exec_20261027'))
from ui_interactive_tx import build_frame,load_manifest
sys.path.insert(0,str(root.parent/'AMR_Rescue_20261025'))
import pluto_link_probe as link
import pilot_recovery as public
manifest=root.parent/'嵌赛/rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json'
dataset=root.parent/'嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset'
rows=load_manifest(manifest)
if a.mode=='smoke24':
    seen=set();selected=[]
    for r in rows:
        label=int(r['file'].split('_')[0])
        if label not in seen:selected.append(r);seen.add(label)
    rows=selected
assert len(rows)==(24 if a.mode=='smoke24' else 240)
plan=dict(kind='INDEPENDENT_TX_V1',mode=a.mode,no_rx_connection=True,
          hold_sec=a.hold_sec,mute_sec=a.mute_sec,warmup_sec=a.warmup_sec,center_hz=a.center_hz,
          scoring='First RX capture in [TX_start+1.5s,TX_end-0.3s]; missing counts wrong; fixed denominator',
          records=rows)
(a.out/'plan_private.json').write_text(json.dumps(plan,indent=2))
uris=link.scan_usb()
if len(uris)!=1:raise RuntimeError('Expected one TX Pluto: '+repr(uris))
radio=link.Radio(uris[0]);buffer=None;restore=[]
try:
    for ch,key,value in [(radio.tx,'hardwaregain',-40),(radio.tx,'sampling_frequency',2560000),
                         (radio.tx,'rf_bandwidth',18000000),(radio.tlo,'frequency',a.center_hz)]:
        radio.set(ch,key,value)
    time.sleep(a.mute_sec)
    if a.warmup_sec:
        raw=(dataset/rows[0]['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=rows[0]['source_sha256']:raise RuntimeError('warmup SHA mismatch')
        buffer=radio.send(build_frame(raw,public.train,public.tail))
        warmup_start=time.time_ns()
        print('TX_WARMUP start_ns=%d seconds=%s'%(warmup_start,a.warmup_sec),flush=True)
        time.sleep(a.warmup_sec);radio.stop(buffer);buffer=None
        (a.out/'warmup.json').write_text(json.dumps(dict(start_ns=warmup_start,end_ns=time.time_ns())))
    with (a.out/'events_private.jsonl').open('w') as log:
        for index,r in enumerate(rows):
            raw=(dataset/r['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=r['source_sha256']:raise RuntimeError('payload SHA mismatch')
            frame=build_frame(raw,public.train,public.tail)
            buffer=radio.send(frame);begin=time.time_ns()
            print('TX index=%d class=%s center=%d'%(index,r['file'].split('_')[0],a.center_hz),flush=True)
            time.sleep(a.hold_sec)
            radio.stop(buffer);buffer=None;end=time.time_ns()
            record=dict(r,index=index,label=int(r['file'].split('_')[0]),start_ns=begin,end_ns=end)
            log.write(json.dumps(record)+'\n');log.flush()
            time.sleep(.25)
    print('TX_MUTED',flush=True);time.sleep(a.mute_sec)
finally:
    if buffer is not None:radio.stop(buffer)
    restore=radio.close()
    (a.out/'restore.json').write_text(json.dumps(restore))
print('TX_COMPLETE records=%d restore_errors=%d'%(len(rows),len(restore)),flush=True)
