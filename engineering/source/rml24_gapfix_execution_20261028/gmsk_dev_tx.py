"""48 development sources only; cannot run formal 240+240 validation."""
import argparse,hashlib,json,sys,time
from pathlib import Path
r=Path(__file__).parent.parent/'rml24_mainchain_diagnostic_20261028'
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(r.parent/'scan_exec_20261027'))
from ui_interactive_tx import build_frame
sys.path.insert(0,str(r.parent/'AMR_Rescue_20261025'))
import pluto_link_probe as link
import pilot_recovery as public
dataset=r.parent/'嵌赛/amr_rescue_gmsk_candidate_20261026/development_seed4100000'
doc=json.loads((dataset/'expected_private.json').read_text(encoding='utf-8'))
rows=[v for v in doc['records'] if v['class_index'] in [16,19,22]]
assert len(rows)==15
validation=json.loads((r.parent/'嵌赛/amr_rescue_gmsk_candidate_20261026/validation_seed5100000/expected_private.json').read_text(encoding='utf-8'))
assert not set(v['source_sha256'] for v in rows)&set(v['source_sha256'] for v in validation['records'])
(a.out/'plan_private.json').write_text(json.dumps(dict(kind='DEVELOPMENT_DIAGNOSTIC_48_NOT_FORMAL_VALIDATION',
   hold_sec=4,mute_sec=8,records=rows),indent=2),encoding='utf-8')
uris=link.scan_usb()
if len(uris)!=1:raise RuntimeError('Need exactly one TX Pluto '+repr(uris))
radio=link.Radio(uris[0]);buffer=None
try:
    for ch,key,value in [(radio.tx,'hardwaregain',-40),(radio.tx,'sampling_frequency',2560000),
                         (radio.tx,'rf_bandwidth',18000000),(radio.tlo,'frequency',2400000000)]:radio.set(ch,key,value)
    time.sleep(8)
    with (a.out/'events_private.jsonl').open('w',encoding='utf-8') as f:
        for index,v in enumerate(rows):
            raw=(dataset/v['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=v['source_sha256']:raise RuntimeError('SHA mismatch')
            buffer=radio.send(build_frame(raw,public.train,public.tail));begin=time.time_ns()
            print('DEVELOPMENT_TX %d/48'%(index+1),flush=True);time.sleep(4)
            radio.stop(buffer);buffer=None;end=time.time_ns()
            f.write(json.dumps(dict(index=index,file=v['file'],source_sha256=v['source_sha256'],
                    label=v['class_index'],seed=v['seed'],start_ns=begin,end_ns=end))+'\n');f.flush();time.sleep(.25)
    time.sleep(8)
finally:
    if buffer is not None:radio.stop(buffer)
    errors=radio.close();(a.out/'restore.json').write_text(json.dumps(errors))
print('DEVELOPMENT_TX_COMPLETE n=15',flush=True)
