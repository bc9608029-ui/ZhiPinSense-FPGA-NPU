import argparse,json,socket,time,sys,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,'/root/amr_rescue_20261025')
from pluto_link_probe import Radio,scan_usb
import pilot_recovery as baseline
sys.path.insert(0,str(Path(__file__).resolve().parent))
import candidate_two_dc as candidate
ap=argparse.ArgumentParser();ap.add_argument('--socket',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
out=Path(a.out);out.mkdir(exist_ok=False);uris=scan_usb();assert len(uris)==1,uris;r=Radio(uris[0]);npu=None;control=None;rows=[]
def exact(sock,n):
 chunks=[]
 while n:
  b=sock.recv(n)
  if not b:raise RuntimeError('NPU stream closed')
  chunks.append(b);n-=len(b)
 return b''.join(chunks)
try:
 r.config_rx();npu=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);npu.settimeout(20);npu.connect(a.socket);control=socket.create_connection(('192.168.126.50',39012),timeout=30);cf=control.makefile('rwb',buffering=0)
 while True:
  cf.write(b'NEXT\n');msg=json.loads(cf.readline())
  if msg.get('done'):break
  seq=msg['seq'];row={'seq':seq,'arms':{}};start=time.monotonic();y=r.receive(65536);np.save(out/('%04d.raw.npy'%seq),y);cf.write(b'CAPTURED\n');assert json.loads(cf.readline()).get('stopped')
  for name,mod in [('baseline',baseline),('candidate',candidate)]:
   arm={}
   try:
    x,meta=mod.recover(y);arm.update(meta);tensor=np.stack([x.real,x.imag],axis=1).astype('<f4');assert tensor.shape==(8,2,1024) and np.isfinite(tensor).all();data=tensor.tobytes();(out/('%04d.%s.inputs.bin'%(seq,name))).write_bytes(data)
    logits=[]
    for inp in tensor:
     npu.sendall(inp.tobytes());logits.append(np.frombuffer(exact(npu,96),dtype='<f4').copy())
    logits=np.stack(logits);assert np.isfinite(logits).all();arm.update(pred=int(logits.mean(0).argmax()),predictions=logits.argmax(1).tolist(),logits=logits.mean(0).tolist(),input_sha256=hashlib.sha256(data).hexdigest())
   except Exception as e:arm['error']=str(e)
   row['arms'][name]=arm
  row['elapsed_ms']=(time.monotonic()-start)*1000;rows.append(row);(out/'results.json').write_text(json.dumps(dict(kind='PAIRED_SAME_CAPTURE_FROZEN_NPU',receiver_has_labels=False,records=rows),indent=2));print(json.dumps(dict(seq=seq,baseline=row['arms']['baseline'].get('pred'),candidate=row['arms']['candidate'].get('pred'))),flush=True)
finally:
 if control:control.close()
 if npu:npu.close()
 errors=r.close();(out/'restore.json').write_text(json.dumps(errors))
print('PAIRED_RX_COMPLETE',len(rows),flush=True)