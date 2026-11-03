from pathlib import Path
import subprocess,time,json,re,gzip,base64
p=Path(__file__).parent
for _ in range(400):
 d=json.loads((p/'STATUS.json').read_text()) if (p/'STATUS.json').exists() else {}
 if d.get('stage')=='RF_COMPLETE_CLASSIFICATION_STARTED':break
 if d.get('stage')=='FAILED':raise RuntimeError(d)
 time.sleep(5)
assert d.get('stage')=='RF_COMPLETE_CLASSIFICATION_STARTED'
query="python3 -c \"import json,gzip,base64;from pathlib import Path;p=Path('/root/rml24_reduced_repeat_followup_20261101/CLASSIFICATION_RESULT.json');print('WAIT') if not p.exists() else print('DATA_BEGIN'+base64.b64encode(gzip.compress(json.dumps([dict(mode=Path(x['folder']).name,m=x['capture_mono_ns'],ok=x['recovered'],pred=x.get('prediction',{}).get('pred'),repeat=x.get('metadata',{}).get('detected_repeats')) for x in json.loads(p.read_text())['rows']]).encode())).decode()+'DATA_END')\""
for _ in range(50):
 r=subprocess.run(['powershell','-NoProfile','-File','E:/scan_exec_20261027/serial.ps1','-Command',query,'-Seconds','3'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT);t=r.stdout.decode('utf8',errors='replace');(p/'EXPORT_LAST.txt').write_text(t);m=re.search(r'DATA_BEGIN([A-Za-z0-9+/=\s]+)DATA_END',t)
 if m:break
 time.sleep(15)
assert m;rows=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',m.group(1)))));(p/'CLASSIFICATION_ROWS.json').write_text(json.dumps(rows,indent=2));results=[]
for mode in ['gainfreeze']:
 a=json.loads((p/(mode+'_CLOCK_PRE.json')).read_text());b=json.loads((p/(mode+'_CLOCK_POST.json')).read_text());assert a['board_boot_id']==b['board_boot_id'] and max(a['uncertainty_ns'],b['uncertainty_ns'])<250000000 and abs(a['offset_ns']-b['offset_ns'])<100000000;o=(a['offset_ns']+b['offset_ns'])//2;ev=json.loads((p/mode/'VARIABLE_TX_EVENTS.json').read_text());assert len(ev)==48;scores=[]
 for e in ev:
  c=[x for x in rows if x['mode']==mode and e['start_qpc_ns']+1000000000<=x['m']+o<=e['end_qpc_ns']-300000000];x=min(c,key=lambda x:x['m']) if c else None;scores.append(dict(expected=e['class_index'],chosen=x,correct=bool(x and x['ok'] and x['pred']==e['class_index'])))
 results.append(dict(mode=mode,denominator=48,correct=sum(x['correct'] for x in scores),missing=sum(x['chosen'] is None for x in scores),rows=scores))
(p/'SCORE.json').write_text(json.dumps(results,indent=2));(p/'STATUS.json').write_text(json.dumps(dict(stage='COMPLETE_NOT_DEPLOYED',results=[dict(mode=x['mode'],correct=x['correct'],denominator=48) for x in results])));print('PAIRED_SCORE_COMPLETE')
