import sys,time,json,hashlib,subprocess
from pathlib import Path
import numpy as np
r=Path('/root/rml24_three_modes_execution_20261029');out=r/'tx_source_rf02';out.mkdir(exist_ok=False)
sys.path.insert(0,'/root/amr_rescue_20261025');import pluto_link_probe as link
assert hashlib.sha256(Path(link.__file__).read_bytes()).hexdigest()=='1b248f8f391976513c35ca54f31d7daef3fa363e2d095940f9ff17d4d60126a2'
state=subprocess.run(['systemctl','is-active','rml24-receiver'],capture_output=True,text=True).stdout.strip();restore_service=state in ['active','activating'];(out/'original_receiver_state.txt').write_text(state)
radio=None
try:
 subprocess.run(['systemctl','stop','rml24-receiver'],check=True)
 uris=link.scan_usb();assert len(uris)==1,uris;radio=link.Radio(uris[0]);radio.config_rx();radio.set(radio.rx,'sampling_frequency',10240000);radio.set(radio.rlo,'frequency',2401800000)
 config={'uri':uris[0],'sample_rate':radio.get(radio.rx,'sampling_frequency'),'lo':radio.get(radio.rlo,'frequency'),'gain':radio.get(radio.rx,'hardwaregain'),'bw':radio.get(radio.rx,'rf_bandwidth')};assert abs(int(config['sample_rate'])-10240000)<=2;assert abs(int(config['lo'])-2401800000)<=5;(out/'config.json').write_text(json.dumps(config));print('SOURCE_RX_READY',config,flush=True)
 start=time.monotonic();i=0;window=np.hanning(4096)
 with (out/'records.jsonl').open('w') as f:
  while time.monotonic()-start<315:
   z=radio.receive(65536);ts=time.time_ns();iq=np.column_stack((z.real,z.imag)).astype('<i2');raw=iq.tobytes();(out/('%04d.raw.i16'%i)).write_bytes(raw)
   psd=np.mean(abs(np.fft.fftshift(np.fft.fft(z.reshape(-1,4096)*window,axis=1),axes=1))**2,axis=0)
   v=dict(index=i,time_ns=ts,lo_hz=int(config['lo']),sample_rate=int(config['sample_rate']),raw_sha256=hashlib.sha256(raw).hexdigest(),clip_ratio=float(np.mean(abs(iq.astype(np.int32))>=32752)),psd_db=(10*np.log10(np.maximum(psd,1e-30))).tolist());f.write(json.dumps(v)+'\n');f.flush();i+=1;time.sleep(2)
 print('SOURCE_RX_COMPLETE captures='+str(i),flush=True)
finally:
 errors=radio.close() if radio else [];(out/'restore.json').write_text(json.dumps(errors))
 if restore_service:subprocess.run(['systemctl','start','rml24-receiver'],check=True)
 print('SOURCE_RX_RESTORED',errors,flush=True)
