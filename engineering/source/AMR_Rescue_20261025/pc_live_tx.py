"""Controlled cabled transmitter. Receiver gets sequence numbers only, no labels/IQ."""
import argparse,csv,json,socket,time
from pathlib import Path
import numpy as np
from pluto_link_probe import Radio,scan_usb
from pilot_recovery import train,tail

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--session',default='S2',choices=['S1','S2'])
    ap.add_argument('--instances',type=int,default=1);ap.add_argument('--out',required=True)
    ap.add_argument('--bind',default='192.168.126.50');ap.add_argument('--port',type=int,default=39012)
    args=ap.parse_args();assert 1<=args.instances<=10
    out=Path(args.out);out.mkdir(exist_ok=False)
    root=Path('E:/嵌赛/fix10class24_realrf_finetune_pilot1_work/line_a')
    truth={r['source_id']:r for r in csv.DictReader((root/'results/source_manifest_960.tsv').open(encoding='utf-8'),delimiter='\t')}
    tasks=[(ci,i) for ci in range(24) for i in range(args.instances)]
    np.random.default_rng(20261025).shuffle(tasks)
    expected=[]
    for seq,(ci,i) in enumerate(tasks):
        sid='%s_c%02d_i%02d'%(args.session.lower(),ci,i)
        expected.append({'seq':seq,'source_id':sid,'class_index':ci,'class_name':truth[sid]['class_name']})
    (out/'expected_private.json').write_text(json.dumps(expected,indent=2))
    uris=scan_usb();assert len(uris)==1,uris
    radio=Radio(uris[0]);listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind((args.bind,args.port));listener.listen(1);listener.settimeout(180)
    current=None
    try:
        radio.set(radio.tx,'hardwaregain',-40)
        radio.set(radio.tx,'sampling_frequency',2560000);radio.set(radio.tx,'rf_bandwidth',18000000)
        radio.set(radio.tlo,'frequency',2400000000)
        print('TX_LISTENING',args.bind,args.port,flush=True)
        conn,addr=listener.accept();conn.settimeout(30)
        with conn:
            cf=conn.makefile('rwb',buffering=0)
            for item in expected:
                assert cf.readline()==b'NEXT\n'
                iq=np.fromfile(root/'inputs'/args.session/(item['source_id']+'.bin'),dtype='<f4').reshape(2,1024)
                source=iq[0]+1j*iq[1]
                frame=np.concatenate([np.zeros(2048),train,np.tile(source,8),tail,np.zeros(2048)])
                scale=min(68.46059377833956,1600/max(abs(frame.real).max(),abs(frame.imag).max()))
                current=radio.send(frame*scale);time.sleep(.08)
                cf.write((json.dumps({'seq':item['seq']})+'\n').encode())
                assert cf.readline()==b'CAPTURED\n'
                radio.stop(current);current=None;cf.write(b'{"stopped":true}\n')
                print('TX_COMPLETE',item['seq'],flush=True)
            assert cf.readline()==b'NEXT\n';cf.write(b'{"done":true}\n')
    finally:
        if current:radio.stop(current)
        errors=radio.close();listener.close();(out/'restore.json').write_text(json.dumps(errors))
if __name__=='__main__':main()
