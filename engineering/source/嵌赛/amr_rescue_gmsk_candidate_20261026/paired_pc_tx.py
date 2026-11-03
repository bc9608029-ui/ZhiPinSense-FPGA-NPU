import argparse,json,socket,time,sys,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,'E:/AMR_Rescue_20261025')
from pluto_link_probe import Radio,scan_usb
from pilot_recovery import train,tail
ap=argparse.ArgumentParser();ap.add_argument('--dataset',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
dataset=Path(a.dataset);out=Path(a.out);out.mkdir(exist_ok=False)
doc=json.loads((dataset/'expected_private.json').read_text());records=doc['records'];(out/'expected_private.json').write_bytes((dataset/'expected_private.json').read_bytes())
uris=scan_usb();assert len(uris)==1,uris;r=Radio(uris[0]);listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('192.168.126.50',39012));listener.listen(1);listener.settimeout(180);buffer=None
try:
 r.set(r.tx,'hardwaregain',-40);r.set(r.tx,'sampling_frequency',2560000);r.set(r.tx,'rf_bandwidth',18000000);r.set(r.tlo,'frequency',2400000000)
 print('PAIRED_TX_LISTENING',len(records),flush=True);conn,peer=listener.accept();conn.settimeout(30)
 with conn:
  cf=conn.makefile('rwb',buffering=0)
  for item in records:
   assert cf.readline()==b'NEXT\n'
   data=(dataset/item['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==item['source_sha256']
   iq=np.frombuffer(data,dtype='<f4').reshape(2,1024);source=iq[0]+1j*iq[1]
   frame=np.concatenate([np.zeros(2048,dtype=np.complex64),train,np.tile(source,8),tail,np.zeros(2048,dtype=np.complex64)]).astype(np.complex64)
   scaled=frame*68.46059377833956;assert max(abs(scaled.real).max(),abs(scaled.imag).max())<=2047
   buffer=r.send(scaled);time.sleep(.08);cf.write((json.dumps({'seq':item['seq']})+'\n').encode());assert cf.readline()==b'CAPTURED\n';r.stop(buffer);buffer=None;cf.write(b'{"stopped":true}\n')
   print('TX',item['seq'],flush=True)
  assert cf.readline()==b'NEXT\n';cf.write(b'{"done":true}\n')
finally:
 if buffer:r.stop(buffer)
 errors=r.close();listener.close();(out/'restore.json').write_text(json.dumps(errors));print('TX_RESTORE',errors,flush=True)