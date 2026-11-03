from pathlib import Path
import gzip,json,numpy as np,re
r=Path(r'E:\rml24_three_modes_execution_20261029');e=json.loads(gzip.decompress((r/'multifreq_sweep01_evidence.json.gz').read_bytes()));tx=json.loads((r/'multifreq_sweep01_pc/transmit_run.json').read_text());clock=json.loads((r/'multifreq_sweep_clock.json').read_text(encoding='utf-8-sig'));offset=int(clock['offset_ns']);ph=[]
for v in tx['events']:
 if v['event']=='active':ph.append(dict(phase=v['phase'],start_ns=v['wall_ns']))
 elif v['event']=='stop' and ph:ph[-1]['end_ns']=v['wall_ns']
summary=[]
for p in ph:
 g=[v for v in e['rows'] if p['start_ns']+2000000000 <= v['capture_time_ns']+offset <= p['end_ns']-500000000];valid=[v for v in g if v['finite']];groups=[]
 for label,hz in [(3,2400000000),(9,2403600000)]:
  a=[v for v in valid if abs(v['center_hz']-hz)<=10000];groups.append(dict(label=label,center_hz=hz,captures=len(a),correct=sum(v['pred']==label for v in a),first_latency_sec=(a[0]['capture_time_ns']+offset-p['start_ns'])/1e9 if a else None))
 extra=[dict(center_hz=v['center_hz'],pred=v['pred'],frame_id=v['frame_id']) for v in valid if min(abs(v['center_hz']-2400000000),abs(v['center_hz']-2403600000))>10000]
 summary.append(dict(phase=p['phase'],records=len(g),valid=len(valid),main_groups=groups,extra_valid=extra))
starts=[v['capture_time_ns'] for v in e['rows'] if any(s.get('scan_index')==1 for s in v['scan_steps'])];cycles=np.diff(starts)/1e9
out=dict(kind='MULTIFREQUENCY_SWEEP_SHORT_NOT_FORMAL_ACCURACY',phases=summary,final=e['final'],supervisor=e['supervisor'],npu_stop=e['npu_stop'],history=e['history'],full_cycle_sec={'min':float(cycles.min()),'median':float(np.median(cycles)),'max':float(cycles.max())} if len(cycles) else None,tx_restore_ok=tx['restore_ok'],tx_restore_errors=tx['restore_errors'])
assert e['final']['restore_errors']==[] and e['supervisor']['stop_errors']==[];assert all(v['repeat_average']==8 for v in e['rows'] if v['finite'])
(r/'MULTIFREQ_SWEEP_ANALYSIS.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
