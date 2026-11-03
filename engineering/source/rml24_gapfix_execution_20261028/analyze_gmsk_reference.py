import json,tarfile,numpy as np
from pathlib import Path
r=Path('/root/rml24_mainchain_diagnostic_20261028');run=r/'diag_gmsk02'
refs=[]
with tarfile.open(str(r/'gmsk_clean_blind.tar.gz')) as t:
 for m in sorted(t.getmembers(),key=lambda x:x.name):
  q=np.frombuffer(t.extractfile(m).read(),dtype='<f4').reshape(2,1024);refs.append(q[0]+1j*q[1])
replay={v['frame_id']:v for v in json.loads((r/'gmsk_mean_replay02/results.json').read_text())}
rows=[]
for v in [json.loads(x) for x in (run/'capture/records.jsonl').read_text().splitlines()]:
 if not v['candidate']['finite']:continue
 f=v['frame_id'];q=np.fromfile(str(run/'evidence'/('%06d.inputs.bin'%f)),dtype='<f4').reshape(8,2,1024);z=q[:,0]+1j*q[:,1];y=z.mean(axis=0,dtype=np.complex128);yc=y-y.mean();den=max(float(np.vdot(y,y).real),1e-30);matches=[]
 for i,x in enumerate(refs):
  xc=x-x.mean();a=np.vdot(xc,yc)/max(float(np.vdot(xc,xc).real),1e-30);b=y.mean()-a*x.mean();e=y-a*x-b
  matches.append((float(np.vdot(e,e).real/den),i,float(abs(b)/np.sqrt(den/1024))))
 matches.sort();raw=np.fromfile(str(run/'evidence'/('%06d.raw.i16'%f)),dtype='<i2')
 rows.append(dict(frame=f,reference=matches[0][1],affine_nmse=matches[0][0],next_nmse=matches[1][0],offset_fraction=matches[0][2],baseline_pred=v['candidate']['pred'],mean_pred=replay[f]['result']['pred'],repeat_noise=float(np.mean(abs(z-y)**2)/max(np.mean(abs(y)**2),1e-30)),raw_clip_fraction=float(np.mean(abs(raw.astype(np.int32))>=32752)),cfo_hz=v['candidate'].get('cfo_hz')))
out=dict(kind='OFFLINE_NEAREST_REFERENCE_DIAGNOSTIC_NOT_TIME_LABEL_TRUTH',rows=rows)
(run/'nearest_reference_analysis.json').write_text(json.dumps(out,indent=2))
for ref in sorted(set(v['reference'] for v in rows)):
 g=[v for v in rows if v['reference']==ref];print(json.dumps(dict(reference=ref,n=len(g),baseline_preds=[v['baseline_pred'] for v in g],mean_preds=[v['mean_pred'] for v in g],median_affine_nmse=float(np.median([v['affine_nmse'] for v in g])),median_repeat_noise=float(np.median([v['repeat_noise'] for v in g])),max_clip=max(v['raw_clip_fraction'] for v in g))))
