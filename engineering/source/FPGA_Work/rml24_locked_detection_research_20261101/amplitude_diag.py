from pathlib import Path
import sys,json,gzip,numpy as np,base64
root=Path('/root/rml24_locked_detection_research_20261101');sys.path.insert(0,'/root/rml24_gainfreeze_integration_20261101/candidate/candidate/rml24_final/recovery');import candidate_two_dc as rec
bank=np.frombuffer(gzip.decompress((Path(__file__).parent/'PURE_QUANT_INPUTS.gz').read_bytes()),dtype='<f4').reshape(-1,8,2,1024)
indices={6: 0, 7: 0, 8: 0, 9: 0, 12: 3, 13: 3, 14: 3, 17: 6, 18: 6, 19: 6, 22: 9, 23: 9, 24: 9, 27: 12, 28: 12, 29: 12, 32: 15, 33: 15, 34: 15, 35: 15}
rows=[]
for index,source in indices.items():
 a=bank[source,0,0]+1j*bank[source,0,1];x,_=rec.recover(np.load(root/('raw_%03d.npy'%index)));z=x.mean(axis=0);design=np.column_stack([a,np.ones(1024)]);coef=np.linalg.lstsq(design,z,rcond=None)[0];res=float(np.linalg.norm(z-design@coef)/max(np.linalg.norm(z-z.mean()),1e-12));rows.append(dict(index=index,gain_abs=float(abs(coef[0])),gain_phase=float(np.angle(coef[0])),dc_abs=float(abs(coef[1])),relative_error=float(np.linalg.norm(z-a)/max(np.linalg.norm(a),1e-12)),fit_relative_error=res))
(root/'AMPLITUDE_DIAG.json').write_text(json.dumps(rows,indent=2));print('AMP_BEGIN'+base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode()+'AMP_END')
