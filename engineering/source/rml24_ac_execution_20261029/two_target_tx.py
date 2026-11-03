import sys,json,hashlib,time
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
r=Path(r'E:\rml24_ac_execution_20261029');sys.path.insert(0,r'E:\scan_exec_20261027');from ui_interactive_tx import build_frame,load_manifest
sys.path.insert(0,r'E:\AMR_Rescue_20261025');import pluto_link_probe as link;import pilot_recovery as public
common=r.parent/('\u5d4c\u8d5b');manifest=common/'rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json';dataset=common/'rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset'
rows=load_manifest(manifest);selected=[next(v for v in rows if int(v['file'].split('_')[0])==c) for c in [3,9]]
fs=10240000;waves=[]
for v,df in zip(selected,[-1800000,1800000]):
 data=(dataset/v['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==v['source_sha256'];base=build_frame(data,public.train,public.tail);z=resample_poly(base,4,1);waves.append(z*np.exp(2j*np.pi*df*np.arange(len(z))/fs))
composite=sum(waves);peak=float(max(abs(composite.real).max(),abs(composite.imag).max()));assert peak<2047,peak
report=dict(kind='SIMULTANEOUS_TWO_RF_CENTERS_NOT_240_REGRESSION',tx_center_hz=2401800000,sample_rate=fs,signal_centers_hz=[2400000000,2403600000],records=selected,composite_sha256=hashlib.sha256(composite.astype('<c8').tobytes()).hexdigest(),peak_component_before_x16=peak,clipping=False,rf_started=False)
(r/'two_target01_private.json').write_text(json.dumps(report,indent=2));print('OFFLINE_COMPOSITE_READY',json.dumps(report),flush=True)
if '--transmit' not in sys.argv:sys.exit(0)
uris=link.scan_usb();assert len(uris)==1,uris
radio=link.Radio(uris[0]);buffer=None
try:
 for ch,key,value in [(radio.tx,'hardwaregain',-40),(radio.tx,'sampling_frequency',fs),(radio.tx,'rf_bandwidth',18000000),(radio.tlo,'frequency',2401800000),(radio.tlo,'powerdown',0)]:radio.set(ch,key,value)
 for name,z,seconds in [('both',composite,120),('only_first',waves[0],60)]:
  buffer=radio.send(z);print('TX_PHASE',name,time.time_ns(),flush=True);time.sleep(seconds);radio.stop(buffer);buffer=None
 print('TX_PHASE muted',time.time_ns(),flush=True);time.sleep(30)
finally:
 if buffer is not None:radio.stop(buffer)
 errors=radio.close();(r/'two_target01_restore.json').write_text(json.dumps(errors));print('TX_DONE',errors,flush=True)
