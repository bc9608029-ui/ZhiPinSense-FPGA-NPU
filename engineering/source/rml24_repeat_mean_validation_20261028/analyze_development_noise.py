"""Explain the frozen candidate using existing development data only."""
import gzip,json
from pathlib import Path
import numpy as np
r=Path(__file__).parent;d=r.parent/'rml24_mainchain_diagnostic_20261028'
rows=json.loads((d/'IQ_DIAGNOSTIC.json').read_text(encoding='utf-8'))['rows']
mean={v['frame_id']:v for v in json.loads(gzip.decompress((d/'mean_replay01.json.gz').read_bytes()))['results']}
groups={True:[],False:[]}
for row in rows:
    if row.get('event_index') is None or not row['finite']:continue
    h=np.load(d/'board/diag_fixed01/evidence'/('%06d.response.npy'%row['frame_id']))
    power=abs(h)**2;inv=np.conj(h)/(power+1e-4*float(power.max()))
    noise_gain=float(np.mean(abs(inv)**2)*np.median(power))
    groups[row['correct']].append(dict(frame_id=row['frame_id'],
                  repeat_noise_fraction=1-mean[row['frame_id']]['repeat_coherence'],
                  normalized_inverse_noise_gain=noise_gain))
out=dict(kind='EXISTING_DEVELOPMENT_DATA_ONLY_NOT_RF_VALIDATION_RESULT',groups={})
for correct,values in groups.items():
    out['groups'][str(correct)]=dict(n=len(values),
        median_repeat_noise_fraction=float(np.median([v['repeat_noise_fraction'] for v in values])),
        median_normalized_inverse_noise_gain=float(np.median([v['normalized_inverse_noise_gain'] for v in values])))
(r/'DEVELOPMENT_NOISE_DIAGNOSTIC.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
