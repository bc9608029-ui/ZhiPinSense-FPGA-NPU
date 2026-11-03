import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
"""Independent RX-only raw capture. No TX notification or labels.

Run only on board after stopping competing RX services. No model or FPGA change.
"""
import argparse,hashlib,importlib.util,json,sys,time
from pathlib import Path
import numpy as np
from gain_control import configure,snapshot

LINK_SHA='1b248f8f391976513c35ca54f31d7daef3fa363e2d095940f9ff17d4d60126a2'
def load_link(path):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=LINK_SHA:raise ValueError('legacy Radio SHA mismatch')
    spec=importlib.util.spec_from_file_location('experiment_radio',path)
    link=importlib.util.module_from_spec(spec);spec.loader.exec_module(link);return link

def capture(radio,out,mode,gain,count,settle_seconds=1.0):
    out=Path(out);out.mkdir(exist_ok=False)
    originals={k:radio.get(radio.rx,k) for k in ['gain_control_mode','hardwaregain','sampling_frequency','rf_bandwidth']}
    result=dict(mode=mode,gain_requested=gain,raw_records=0,restore_errors=[],originals=originals)
    try:
        radio.config_rx() # frozen Fs, bandwidth and initial centre
        result['applied']=configure(radio,mode,gain,settle_seconds)
        for _ in range(2):radio.receive(65536)
        with (out/'captures.jsonl').open('w',encoding='utf-8') as log:
            for i in range(count):
                before=snapshot(radio);started=time.time_ns()
                raw=np.asarray(radio.receive(65536))
                after=snapshot(radio)
                if raw.ndim!=1 or len(raw)!=65536 or not np.iscomplexobj(raw) or not np.isfinite(raw).all():
                    raise RuntimeError('invalid/short raw capture')
                name='%06d.raw.npy'%i;np.save(out/name,raw)
                row=dict(record_id=i,capture_start_ns=started,capture_end_ns=time.time_ns(),
                         gain_before=before,gain_after=after,file=name,
                         sha256=hashlib.sha256((out/name).read_bytes()).hexdigest())
                # Endpoint gain readbacks do NOT prove absence of within-frame gain changes.
                log.write(json.dumps(row)+'\n');log.flush();result['raw_records']+=1
    except BaseException as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        try:result['restore_errors']=radio.close() or []
        except Exception as exc:result['restore_errors']=[str(exc)]
        (out/'capture_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--link',type=Path,required=True)
    p.add_argument('--rx-uri',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mode',choices=['manual','slow_attack'],required=True);p.add_argument('--gain',type=float)
    p.add_argument('--count',type=int,default=120);a=p.parse_args()
    if a.count<=0:raise ValueError('positive count required')
    if a.mode=='manual' and a.gain is None:raise ValueError('--gain required for manual')
    link=load_link(a.link)
    if a.rx_uri not in link.scan_usb():raise ValueError('explicit RX URI not found')
    r=capture(link.Radio(a.rx_uri),a.out,a.mode,a.gain,a.count)
    # Fresh get-only context validates restoration; do not merely trust writes.
    check=link.Radio(a.rx_uri)
    try:
        restored={k:check.get(check.rx,k) for k in r['originals']}
        ok=True
        for k,v in r['originals'].items():
            if k=='gain_control_mode':ok=ok and restored[k].strip()==v.strip()
            elif k=='hardwaregain' and r['originals']['gain_control_mode'].strip()!='manual':continue
            else:ok=ok and abs(float(restored[k].split()[0])-float(v.split()[0]))<=.1
    finally:check.close()
    report=dict(readback=restored,restore_verified=ok,write_errors=r['restore_errors'])
    (a.out/'restore_readback.json').write_text(json.dumps(report,indent=2))
    if not ok or r['restore_errors']:raise RuntimeError('device restoration failed')

if __name__=='__main__':main()
