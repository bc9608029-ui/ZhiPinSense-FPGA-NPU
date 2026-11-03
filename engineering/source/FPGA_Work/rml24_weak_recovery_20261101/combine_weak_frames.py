from pathlib import Path
import sys,json,numpy as np
from scipy.signal import correlate,find_peaks
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');sys.path.insert(0,str(base));from adaptive_repeat_recovery import recover_auto,train
root=Path('/root/rml24_weak_recovery_20261101');folder=Path('/root/rml24_gain_range_validation_20261101/gainfreeze_bw5');records=json.loads((folder/'CAPTURE_RESULT.json').read_text())['rows'];lookup={x['capture_mono_ns']:x for x in records};selected=json.loads((base/'WEAK_SELECTED.json').read_text());out=[]
def combine(y):
 c=abs(correlate(y,train,mode='valid',method='fft'));peaks,_=find_peaks(c,distance=14000);peaks=sorted([int(k) for k in peaks if k+12288<=len(y)],key=lambda k:c[k],reverse=True)[:4]
 if len(peaks)<2:raise RuntimeError('fewer than2 candidate repeated frames')
 estimates=[]
 for k in peaks:
  u=y[k:k+1024];v=y[k+1024:k+2048];estimates.append(np.angle(np.vdot(u-u.mean(),v-v.mean()))*2560000/(2*np.pi*1024))
 freq=float(np.median(estimates));n=np.arange(12288);segments=[]
 for k in peaks:
  z=y[k:k+12288]*np.exp(-2j*np.pi*freq*n/2560000);a=np.vdot(train,z[:2048]);segments.append(z*np.exp(-1j*np.angle(a)))
 z=np.mean(segments,axis=0);scale=128/max(float(np.sqrt(np.mean(abs(z-z.mean())**2))),1e-12);return np.r_[np.zeros(2048),z*scale,np.zeros(2048)].astype(np.complex64),len(peaks)
for item in selected:
 c=lookup[item['m']];y=np.load(folder/c['file']);d=dict(m=item['m'],gain=item['gain'],file=c['file'],original=c['recovered'])
 try:
  z,count=combine(y);x,meta=recover_auto(z);name='combined_'+c['file'];np.save(root/name,z);d.update(recovered=True,frames=count,metadata=meta,combined_file=name)
 except RuntimeError as e:d.update(recovered=False,error=str(e))
 out.append(d);(root/'COMBINE_PROGRESS.json').write_text(json.dumps(out,indent=2))
neg=[];rng=np.random.default_rng(110130)
for i in range(12):
 try:z,n=combine((rng.normal(size=65536)+1j*rng.normal(size=65536)).astype(np.complex64));recover_auto(z);neg.append(True)
 except RuntimeError:neg.append(False)
(root/'COMBINE_RESULT.json').write_text(json.dumps(dict(rows=out,synthetic_noise_false_accept=neg,requires_temporally_repeated_frames=True),indent=2));print('COMBINE_DONE',flush=True)
