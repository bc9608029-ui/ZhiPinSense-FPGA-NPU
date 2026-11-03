"""Targeted DC-tracking diagnosis. Ten existing AM-DSB-WC sources, PC only truth."""
import argparse,hashlib,json,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
r=Path(__file__).parent;a.out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(r.parent/'scan_exec_20261027'))
from ui_interactive_tx import load_manifest,build_frame
sys.path.insert(0,str(r.parent/'AMR_Rescue_20261025'))
import pluto_link_probe as link
import pilot_recovery as public
manifest=r.parent/'嵌赛/rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json'
dataset=r.parent/'嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset'
rows=[v for v in load_manifest(manifest) if int(v['file'].split('_')[0])==19]
assert len(rows)==10
(a.out/'plan_private.json').write_text(json.dumps(dict(kind='TARGETED_DC_DIAGNOSTIC_NOT_FORMAL_ACCURACY',
       hold_sec=6,warmup_sec=0,center_hz=2400000000,records=rows),indent=2))
uris=link.scan_usb()
if len(uris)!=1:raise RuntimeError(uris)
radio=link.Radio(uris[0]);buffer=None
try:
    for ch,key,value in [(radio.tx,'hardwaregain',-40),(radio.tx,'sampling_frequency',2560000),
                        (radio.tx,'rf_bandwidth',18000000),(radio.tlo,'frequency',2400000000)]:radio.set(ch,key,value)
    time.sleep(8)
    with (a.out/'events_private.jsonl').open('w') as log:
        for index,row in enumerate(rows):
            raw=(dataset/row['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=row['source_sha256']:raise RuntimeError('SHA mismatch')
            buffer=radio.send(build_frame(raw,public.train,public.tail));start=time.time_ns()
            print('DC_TX index=%d'%index,flush=True);time.sleep(6)
            radio.stop(buffer);buffer=None;end=time.time_ns()
            log.write(json.dumps(dict(row,index=index,label=19,start_ns=start,end_ns=end))+'\n');log.flush()
            time.sleep(.25)
    time.sleep(8)
finally:
    if buffer is not None:radio.stop(buffer)
    errors=radio.close();(a.out/'restore.json').write_text(json.dumps(errors))
print('DC_TX_COMPLETE',flush=True)
