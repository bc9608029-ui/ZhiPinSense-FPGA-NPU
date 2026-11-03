from pathlib import Path
import json
r=Path(r'E:\rml24_three_modes_execution_20261029');phases=json.loads((r/'reacquire01_events_private.json').read_text());clock=json.loads((r/'reacquire_clock.json').read_text(encoding='utf-8-sig'))
s='''import json,time
from pathlib import Path
r=Path('/root/rml24_three_modes_execution_20261029')
'''+ 'phases='+repr(phases)+'\noffset='+repr(int(clock['offset_ns']))+'\nuncertainty_ms='+repr(clock['uncertainty_ms'])+'''
rows=[json.loads(x) for x in (r/'ui_progress03/capture/records.jsonl').read_text().splitlines()]
anchor=time.time_ns()-int(time.monotonic()*1e9);out={'kind':'SEARCH_LOCK_LOSS_REACQUISITION_FUNCTIONAL_NOT_ACCURACY','clock_uncertainty_ms':uncertainty_ms,'phases':[]}
for p in phases:
 group=[v for v in rows if p['start_ns']+2000000000 <= v['capture_time_ns']+offset <= p['end_ns']-300000000]
 valid=[v for v in group if v['candidate'].get('finite')]
 endgroup=[v for v in rows if p['start_ns'] <= int(v['board_monotonic']*1e9)+anchor+offset <= p['end_ns']]
 out['phases'].append(dict(phase=p['phase'],capture_records=len(group),valid=len(valid),valid_prediction_counts={str(k):sum(v['candidate']['pred']==k for v in valid) for k in sorted(set(v['candidate']['pred'] for v in valid))},rescan_records=sum(any(not q.get('locked_check',False) for q in v['scan_steps']) for v in endgroup)))
post=phases[2];first=next((v for v in rows if v['candidate'].get('finite') and post['start_ns'] <= v['capture_time_ns']+offset <= post['end_ns']),None)
out['first_post_valid_latency_sec']=((first['capture_time_ns']+offset-post['start_ns'])/1e9) if first else None
out['history_text']=(r/'signal_history.txt').read_text();(r/'REACQUIRE_AUDIT.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
'''
(r/'audit_reacquire.py').write_text(s,encoding='ascii')
