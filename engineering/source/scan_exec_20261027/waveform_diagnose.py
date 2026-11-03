import pathlib,json,tarfile,numpy as np
root=pathlib.Path(__file__).parent;base=pathlib.Path('E:/嵌赛/rml24_stage7_execution_20261027');pc=base/'pc/rml24_final_stage7_pc_selftest'
manifest=json.loads((pc/'pc_runtime/selftest_manifest_240.json').read_text(encoding='utf-8'));files={r['seq']:r['file'] for r in manifest['records']}
seqs={0,5,7,57,76,111,149,155,178,183,230,237};means=dict(np.load(root/'selected_means.npz'))
with tarfile.open(base/'waterfall_fix1_final_captures.tar.gz') as tar:
 for m in tar:
  if not m.name.endswith('.candidate.inputs.bin'):continue
  seq=int(pathlib.PurePosixPath(m.name).name.split('.')[0])
  if seq not in seqs:continue
  x=np.frombuffer(tar.extractfile(m).read(),dtype='<f4').reshape(8,2,1024);run='history_r1' if '_r1_' in m.name else 'history_r2';means[f'{run}_{seq}']=(x[:,0]+1j*x[:,1]).mean(axis=0)
rows=[]
for key,y in means.items():
 run,seq=key.rsplit('_',1);seq=int(seq);a=np.fromfile(pc/'dataset'/files[seq],dtype='<f4').reshape(2,1024);x=a[0]+1j*a[1]
 gain=np.vdot(x,y)/np.vdot(x,x);fit=np.column_stack([x,np.conj(x),np.ones(1024)]);coef=np.linalg.lstsq(fit,y,rcond=None)[0]
 den=max(np.linalg.norm(x),1e-12);rows.append({'run':run,'seq':seq,'direct_nrmse':float(np.linalg.norm(y-x)/den),'scalar_fit_nrmse':float(np.linalg.norm(y-gain*x)/den),'affine_iq_fit_nrmse':float(np.linalg.norm(y-fit@coef)/den),'amplitude':float(abs(gain)),'phase_deg':float(np.angle(gain,deg=True)),'dc_error':float(abs(y.mean()-x.mean())),'conjugate_gain':float(abs(coef[1]))})
(root/'selected_waveform_diagnostics.json').write_text(json.dumps(rows,indent=2))
for run in sorted({r['run'] for r in rows}):
 rr=[r for r in rows if r['run']==run];print(run,{k:round(float(np.median([r[k] for r in rr])),5) for k in ['direct_nrmse','scalar_fit_nrmse','affine_iq_fit_nrmse','amplitude','phase_deg','dc_error']})
for seq in [5,7,76,111,237]:print('seq',seq,[(r['run'],round(r['direct_nrmse'],4),round(r['phase_deg'],2),round(r['dc_error'],4)) for r in rows if r['seq']==seq])