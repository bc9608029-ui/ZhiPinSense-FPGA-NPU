from pathlib import Path
import sys,json,time,numpy as np
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');sys.path.insert(0,str(base));from adaptive_repeat_recovery import recover_auto
root=Path('/root/rml24_weak_recovery_20261101');root.mkdir(exist_ok=True);selected=json.loads((base/'WEAK_SELECTED.json').read_text());folder=Path('/root/rml24_gain_range_validation_20261101/gainfreeze_bw5');records=json.loads((folder/'CAPTURE_RESULT.json').read_text())['rows'];lookup={x['capture_mono_ns']:x for x in records};out=[]
for item in selected:
 c=lookup[item['m']];raw=np.load(folder/c['file']);rms=float(np.sqrt(np.mean(abs(raw-raw.mean())**2)));scale=float(np.clip(128/max(rms,1e-12),1/32,1024));d=dict(m=item['m'],gain=item['gain'],file=c['file'],actual_rx_gain=c['actual_gain'],rms=rms,scale=scale,original_recovered=c['recovered'],original_error=c.get('error'))
 try:x,meta=recover_auto(raw*scale);d.update(normalized_recovered=True,metadata=meta)
 except RuntimeError as e:d.update(normalized_recovered=False,error=str(e))
 out.append(d);(root/'PROGRESS.json').write_text(json.dumps(out,indent=2))
rng=np.random.default_rng(110129);negative=[]
for i in range(12):
 raw=(rng.normal(size=65536)+1j*rng.normal(size=65536)).astype(np.complex64)*128
 try:recover_auto(raw);negative.append(dict(index=i,false_accept=True))
 except RuntimeError:negative.append(dict(index=i,false_accept=False))
result=dict(rows=out,synthetic_noise=negative,production_changed=False);(root/'RESULT.json').write_text(json.dumps(result,indent=2));print('WEAK_REPLAY_COMPLETE',flush=True)
