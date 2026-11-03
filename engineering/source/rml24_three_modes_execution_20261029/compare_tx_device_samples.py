from pathlib import Path
import numpy as np,json,hashlib
r=Path(r'E:\rml24_three_modes_execution_20261029');original=r.parent/'\u5d4c\u8d5b'/'rml24_multifreq_tx_validation_20261029/results/tx_dryrun';out=[]
for name in ['a_only','b_only','both','silence']:
 z=np.fromfile(str(r/'tx_verify02_compat'/('wave_'+name+'.c16')),dtype='<c16');q=np.empty((len(z),2),dtype='<i2');q[:,0]=np.round(z.real).astype(np.int16)*16;q[:,1]=np.round(z.imag).astype(np.int16)*16
 old=np.fromfile(str(original/('device_'+name+'.i16')),dtype='<i2').reshape(-1,2);assert q.shape==old.shape
 diff=q.astype(np.int32)-old.astype(np.int32);out.append(dict(scene=name,same_bytes=q.tobytes()==old.tobytes(),different_components=int(np.count_nonzero(diff)),max_abs_int16_difference=int(abs(diff).max()),current_sha256=hashlib.sha256(q.tobytes()).hexdigest(),delivered_sha256=hashlib.sha256(old.tobytes()).hexdigest()))
(r/'TX_DEVICE_SAMPLE_COMPARISON.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
