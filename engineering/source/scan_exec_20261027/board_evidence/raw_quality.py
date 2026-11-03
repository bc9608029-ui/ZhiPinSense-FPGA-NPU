import pathlib,json,hashlib,sys,numpy as np
root=pathlib.Path('/root/rml24_scan_execution_20261027')
report={}
for name in ['fixed_r1','fixed_r2','legacy_control_r1']:
 files=sorted((root/name/'capture').glob('*.raw.npy'))
 rms=[];peaks=[];clip=[]
 for f in files:
  x=np.load(f);rms.append(float(np.sqrt(np.mean(np.abs(x)**2))));peaks.append(float(max(abs(x.real).max(),abs(x.imag).max())));clip.append(int(np.count_nonzero((abs(x.real)>=2047)|(abs(x.imag)>=2047))))
 report[name]={'raw_captures':len(files),'rms_median':float(np.median(rms)),'max_component':max(peaks),'samples_near_12bit_limit':sum(clip)}
sys.path.insert(0,'/root/amr_rescue_20261025');import pluto_link_probe as p
uris=p.scan_usb();report['rx_uris']=uris
r=p.Radio(uris[0])
try:report['rx_readback']={k:r.get(ch,k) for ch,k in [(r.rx,'gain_control_mode'),(r.rx,'hardwaregain'),(r.rx,'sampling_frequency'),(r.rx,'rf_bandwidth'),(r.rlo,'frequency')]}
finally:report['probe_restore_errors']=r.close()
(root/'raw_quality.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))