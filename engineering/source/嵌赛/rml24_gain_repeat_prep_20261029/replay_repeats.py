import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
"""Recover saved raw once, persist unaveraged IQ, infer fixed N=1/2/4/8 arms."""
import argparse,hashlib,importlib.util,json,socket
from pathlib import Path
import numpy as np
from repeat_ablation import average_first

RECOVERY_SHA='e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a'
def exact(s,n):
    chunks=b''
    while len(chunks)<n:
        b=s.recv(n-len(chunks))
        if not b:raise RuntimeError('NPU EOF')
        chunks+=b
    return chunks
def infer(s,t):
    logits=[]
    for x in t:
        s.sendall(x.astype('<f4').tobytes());logits.append(np.frombuffer(exact(s,96),dtype='<f4').copy())
    values=np.asarray(logits)
    if not np.isfinite(values).all():raise RuntimeError('nonfinite NPU logits')
    mean=values.mean(axis=0,dtype=np.float64);return values,int(mean.argmax())
def main():
    p=argparse.ArgumentParser();p.add_argument('--captures',type=Path,required=True)
    p.add_argument('--recovery',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--npu-socket',help='omit to prepare tensors only; no accuracy claimed')
    a=p.parse_args()
    if hashlib.sha256(a.recovery.read_bytes()).hexdigest()!=RECOVERY_SHA:raise ValueError('two-DC SHA mismatch')
    spec=importlib.util.spec_from_file_location('frozen_recovery',a.recovery)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    a.out.mkdir(exist_ok=False);s=None
    if a.npu_socket:s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(30);s.connect(a.npu_socket)
    try:
        with (a.out/'replay.jsonl').open('w') as log:
            for line in (a.captures/'captures.jsonl').read_text().splitlines():
                r=json.loads(line);path=a.captures/r['file']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('raw SHA mismatch')
                row=dict(record_id=r['record_id'],raw_sha256=r['sha256'],arms={})
                try:z,meta=mod.recover(np.load(path,allow_pickle=False))
                except Exception as exc:
                    row['recovery_error']=str(exc)
                    row['arms']={str(n):{'pred':-1,'valid':False} for n in (1,2,4,8)}
                else:
                    t=np.stack([z.real,z.imag],axis=1).astype('<f4')
                    # Validation happens before every arm; no already-averaged input.
                    row.update(stage='RECOVERED_BEFORE_REPEAT_MEAN',repeat_average_applied=False,recovery=meta)
                    t.tofile(a.out/('%06d.unaveraged.bin'%r['record_id']))
                    for n in (1,2,4,8):
                        x=average_first(t,n);data=x.tobytes()
                        arm=dict(valid=True,input_sha256=hashlib.sha256(data).hexdigest(),pred=None)
                        if s:
                            values,pred=infer(s,x);values.tofile(a.out/('%06d.n%d.logits.bin'%(r['record_id'],n)));arm['pred']=pred
                        row['arms'][str(n)]=arm
                log.write(json.dumps(row,allow_nan=False)+'\n');log.flush()
    finally:
        if s:s.close()
if __name__=='__main__':main()
