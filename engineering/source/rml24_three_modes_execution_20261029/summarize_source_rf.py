import json,hashlib,base64,gzip,numpy as np
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029/tx_source_rf02');rows=[];bad=[]
regions={'A':2400000000,'B':2403600000,'A_plus_fs':2402560000,'A_minus_fs':2397440000,'B_plus_fs':2406160000,'B_minus_fs':2401040000}
for line in (r/'records.jsonl').read_text().splitlines():
 v=json.loads(line);p=r/('%04d.raw.i16'%v['index'])
 if hashlib.sha256(p.read_bytes()).hexdigest()!=v['raw_sha256']:bad.append(v['index'])
 psd=np.power(10,np.array(v['psd_db'])/10);freq=np.fft.fftshift(np.fft.fftfreq(len(psd),d=1/v['sample_rate']))+v['lo_hz']
 bands={k:float(np.sum(psd[abs(freq-hz)<=1150000])) for k,hz in regions.items()}
 rows.append(dict(index=v['index'],time_ns=v['time_ns'],clip_ratio=v['clip_ratio'],band_energy=bands))
restore=r/'restore.json';obj=dict(kind='WIDEBAND_RAW_IQ_RF_SOURCE_BAND_ENERGY_NOT_CLASSIFICATION',config=json.loads((r/'config.json').read_text()),rows=rows,raw_sha_failures=bad,restore=json.loads(restore.read_text()) if restore.exists() else None,band_halfwidth_hz=1150000)
(r/'band_energy_summary.json').write_text(json.dumps(obj,indent=2));print('EVIDENCE_BEGIN');print(base64.b64encode(gzip.compress(json.dumps(obj).encode())).decode());print('EVIDENCE_END')
