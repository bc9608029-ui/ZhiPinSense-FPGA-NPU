from pathlib import Path
import json,time,tarfile,hashlib,numpy as np
p=Path(__file__).parent
for _ in range(150):
 if (p/'SWEEP_ARCHIVE_VERIFIED.json').exists():break
 if (p/'TRANSFER_STDERR.log').exists() and 'Traceback' in (p/'TRANSFER_STDERR.log').read_text():raise RuntimeError('transfer failed; analysis not attempted')
 time.sleep(5)
else:raise RuntimeError('archive wait timeout')
proof=json.loads((p/'SWEEP_ARCHIVE_VERIFIED.json').read_text());a=p/'sweep_raw_evidence.tar.gz';assert hashlib.sha256(a.read_bytes()).hexdigest()==proof['archive_sha256']
assets=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console/assets');off=json.loads((p/'sweep6/CLOCK_PRE.json').read_text())['offset_ns'];events=[json.loads(x) for x in (p/'sweep6/sweep6_tx/events_private.jsonl').read_text().splitlines()];out=[];errors=[]
with tarfile.open(str(a),'r:gz') as t:
 records=[json.loads(x) for x in t.extractfile('raw/records.jsonl').read().decode().splitlines()]
 for e in events:
  refi=np.frombuffer((assets/e['file']).read_bytes(),'<f4').reshape(2,1024);ref=refi[0]+1j*refi[1];captures=[]
  for r in records:
   clock=r['capture_monotonic_ns']+off
   if not(e['start_mono_ns']+1500000000<=clock<=e['end_mono_ns']-300000000 and abs(r['center_hz']-2403600000)<=10000):continue
   entry=dict(frame_id=r['frame_id'],prediction=r['candidate']['pred'],correct=r['candidate']['pred']==e['label'],seconds_after_start=(clock-e['start_mono_ns'])/1e9,metadata=r['candidate'],gain=r.get('gain_diagnostic',{}),scan=r['scan_steps'])
   name='raw/%06d.inputs.bin'%r['frame_id']
   try:data=t.extractfile(name).read()
   except KeyError:entry['input_missing']=True
   else:
    x=np.frombuffer(data,'<f4').reshape(8,2,1024);z=(x[:,0,:]+1j*x[:,1,:]).mean(0);mat=np.stack([ref,np.ones(1024)],1);co=np.linalg.lstsq(mat,z,rcond=None)[0];err=z-mat@co;entry.update(input_sha256=hashlib.sha256(data).hexdigest(),aligned_nmse=float(np.mean(abs(err)**2)/np.mean(abs(z-z.mean())**2)),fitted_scale=[float(co[0].real),float(co[0].imag)],fitted_dc=[float(co[1].real),float(co[1].imag)])
   if not entry['correct']:errors.append(dict(window=e['index'],source=e['file'],frame_id=r['frame_id'],pred=entry['prediction'],expected=e['label']))
   captures.append(entry)
  out.append(dict(window=e['index'],source=e['file'],expected=e['label'],captures=captures))
report=dict(diagnostic_only=True,truth_used_posthoc_only=True,windows=out,all_capture_errors=errors,total_centered_captures=sum(len(x['captures']) for x in out),archive_sha256=proof['archive_sha256'],not_deployed=True)
(p/'TARGET_ALL_CAPTURE_ANALYSIS.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(captures=report['total_centered_captures'],errors=errors)),flush=True)
