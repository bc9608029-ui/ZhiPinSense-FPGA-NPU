import argparse,json,socket,sys,time,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent));import candidate_two_dc
ap=argparse.ArgumentParser();ap.add_argument('--socket',required=True);ap.add_argument('--source',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();source=Path(a.source);out=Path(a.out);out.mkdir(exist_ok=False);original=json.loads((source/'results.json').read_text());sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(20);sock.connect(a.socket);rows=[]
def exact(n):
 chunks=[]
 while n:
  b=sock.recv(n)
  if not b:raise RuntimeError('NPU closed')
  chunks.append(b);n-=len(b)
 return b''.join(chunks)
def infer(tensor):
 logits=[]
 for inp in tensor:
  sock.sendall(inp.tobytes());logits.append(np.frombuffer(exact(96),dtype='<f4').copy())
 logits=np.stack(logits);assert np.isfinite(logits).all()
 return dict(pred=int(logits.mean(0).argmax()),predictions=logits.argmax(1).tolist(),logits=logits.mean(0).tolist())
try:
 for old in original['records']:
  seq=old['seq'];row=dict(seq=seq,arms={});t=time.monotonic()
  for arm in ['baseline','candidate']:
   result={}
   try:
    if arm=='baseline':
     data=(source/('%04d.baseline.inputs.bin'%seq)).read_bytes();assert hashlib.sha256(data).hexdigest()==old['arms']['baseline']['input_sha256'];tensor=np.frombuffer(data,dtype='<f4').reshape(8,2,1024).copy()
    else:
     y=np.load(source/('%04d.raw.npy'%seq));x,meta=candidate_two_dc.recover(y);result.update(meta);tensor=np.stack([x.real,x.imag],axis=1).astype('<f4');data=tensor.tobytes();(out/('%04d.candidate.inputs.bin'%seq)).write_bytes(data)
    result.update(infer(tensor));result['input_sha256']=hashlib.sha256(data).hexdigest()
   except Exception as e:result['error']=str(e)
   row['arms'][arm]=result
  row['elapsed_ms']=(time.monotonic()-t)*1000;rows.append(row);(out/'results.json').write_text(json.dumps(dict(kind='SAVED_CAPTURE_REPLAY_REAL_NPU_TWO_DC',records=rows),indent=2));print(seq,row['arms']['baseline'].get('pred'),row['arms']['candidate'].get('pred'),flush=True)
finally:sock.close()
print('REPLAY_COMPLETE',len(rows),flush=True)