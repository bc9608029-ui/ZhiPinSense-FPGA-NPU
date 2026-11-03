import hashlib,json,socket,sys
from pathlib import Path
import numpy as np
r=Path('/root/rml24_standalone_execution_20261027')
sys.path.insert(0,str(r/'candidate/rml24_final/board_runtime'))
from rml24_dualmode_receiver_centered_v2 import infer
inputs=r/'clean_npu_inputs';out=r/'clean_npu_probe'
records=json.loads((inputs/'manifest_public.json').read_text())['records']
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(20);s.connect(str(out/'npu.sock'))
results=[]
try:
    for item in records:
        data=(inputs/item['file']).read_bytes()
        if len(data)!=65536 or hashlib.sha256(data).hexdigest()!=item['input_sha256']:
            raise RuntimeError('Tensor contract failure')
        tensor=np.frombuffer(data,dtype='<f4').reshape(8,2,1024)
        if not np.isfinite(tensor).all():raise RuntimeError('Non-finite clean input')
        result=infer(s,tensor)
        results.append(dict(index=item['index'],input_sha256=item['input_sha256'],result=result))
        print('CLEAN_NPU_PROBE index=%d pred=%d'%(item['index'],result['pred']),flush=True)
finally:
    s.close();(out/'results.json').write_text(json.dumps(results,indent=2))
print('CLEAN_NPU_PROBE_COMPLETE n=%d'%len(results),flush=True)
