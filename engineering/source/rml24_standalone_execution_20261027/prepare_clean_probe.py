"""Prepare label-free board tensor inputs; truth mapping stays on PC."""
import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
r=Path(__file__).parent
b=r.parent/'嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest'
truth=json.loads((b/'truth/expected_private.json').read_text())['records']
seen=set();selected=[]
for item in truth:
    c=item['class_index']
    if c not in seen or c==19:selected.append(item)
    seen.add(c)
assert len(selected)==33
public=[];private=[]
with tarfile.open(r/'clean_npu_inputs_label_free.tar.gz','w:gz') as t:
    for index,item in enumerate(selected):
        payload=(b/'dataset'/item['file']).read_bytes()
        if hashlib.sha256(payload).hexdigest()!=item['source_sha256']:raise RuntimeError('Source SHA mismatch')
        tensor=np.repeat(np.frombuffer(payload,dtype='<f4').reshape(1,2,1024),8,axis=0).astype('<f4').tobytes()
        name='%03d.bin'%index
        info=tarfile.TarInfo(name);info.size=len(tensor);t.addfile(info,io.BytesIO(tensor))
        public.append(dict(index=index,file=name,input_sha256=hashlib.sha256(tensor).hexdigest()))
        private.append(dict(index=index,expected=item['class_index'],source_file=item['file']))
    data=json.dumps(dict(kind='LABEL_FREE_CLEAN_TENSORS',records=public)).encode()
    info=tarfile.TarInfo('manifest_public.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
(r/'clean_npu_probe_truth_PC_ONLY.json').write_text(json.dumps(private,indent=2))
print('CLEAN_PROBE inputs=33 archive_bytes=%d'%(r/'clean_npu_inputs_label_free.tar.gz').stat().st_size)
