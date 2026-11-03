from pathlib import Path
import subprocess,time,json,re,base64,gzip,sys
p=Path(__file__).parent
serial='E:/scan_exec_20261027/serial.ps1'
def ps(args):
 r=subprocess.run(['powershell','-NoProfile','-File']+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);v=r.stdout.decode('utf8',errors='replace');assert r.returncode==0,v;return v
def board(c):return ps([serial,'-Command',c,'-Seconds','3'])
def sync(name):
 text=ps(['E:/FPGA_Work/rml24_timing_fix_20261031/clock_sync_monotonic.ps1']);d=json.loads(text);(p/name).write_text(json.dumps(d,indent=2));return d
try:
 pre=sync('CLOCK_PRE.json')
 (p/'START_CAPTURE.txt').write_text(board('nohup python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/run_24.py > /root/rml24_24class_capture.log 2>&1 < /dev/null &'))
 (p/'START_CLASSIFY.txt').write_text(board('nohup /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 /root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/classify_24.py > /root/rml24_24class_classify.log 2>&1 < /dev/null &'))
 (p/'STATUS.json').write_text(json.dumps(dict(stage='RF_RUNNING',denominator=96)))
 subprocess.run([sys.executable,str(p/'tx_24.py')],check=True,stdout=(p/'TX.log').open('w'),stderr=subprocess.STDOUT)
 post=sync('CLOCK_POST.json');assert pre['board_boot_id']==post['board_boot_id'];assert max(pre['uncertainty_ns'],post['uncertainty_ns'])<250000000;assert abs(pre['offset_ns']-post['offset_ns'])<100000000
 (p/'STATUS.json').write_text(json.dumps(dict(stage='CLASSIFICATION_RUNNING',denominator=96)))
 query="python3 -c \"import json,gzip,base64;from pathlib import Path;p=Path('"+"/root/rml24_repeat_agc_24class_20261101/CLASSIFICATION_RESULT.json"+"');print('WAIT') if not p.exists() else print('DATA_BEGIN'+base64.b64encode(gzip.compress(json.dumps([dict(m=x['capture_mono_ns'],ok=x['recovered'],pred=x.get('prediction',{}).get('pred'),repeat=x.get('metadata',{}).get('detected_repeats')) for x in json.loads(p.read_text())['rows']]).encode())).decode()+'DATA_END')\""
 for _ in range(40):
  text=board(query);(p/'EXPORT_LAST.txt').write_text(text);match=re.search(r'DATA_BEGIN([A-Za-z0-9+/=\s]+)DATA_END',text)
  if match:break
  time.sleep(20)
 assert match,'classification export timeout';rows=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',match.group(1)))));(p/'CLASSIFICATION_ROWS.json').write_text(json.dumps(rows,indent=2));events=json.loads((p/'VARIABLE_TX_EVENTS.json').read_text());assert len(events)==96;score=[];offset=(pre['offset_ns']+post['offset_ns'])//2
 for i,e in enumerate(events):
  candidates=[x for x in rows if e['start_qpc_ns']+1000000000<=x['m']+offset<=e['end_qpc_ns']-300000000];chosen=min(candidates,key=lambda x:x['m']) if candidates else None;score.append(dict(index=i,expected=e['class_index'],expected_repeats=e['repeats'],chosen=chosen,correct=bool(chosen and chosen['ok'] and chosen['pred']==e['class_index']),repeat_correct=bool(chosen and chosen['ok'] and chosen['repeat']==e['repeats'])))
 result=dict(denominator=96,correct=sum(x['correct'] for x in score),repeat_correct=sum(x['repeat_correct'] for x in score),missing=sum(x['chosen'] is None for x in score),rows=score,scope='single frozen message per class, fixed RX fastAGC5MHz; diagnostic not promotion');(p/'SCORE.json').write_text(json.dumps(result,indent=2));(p/'FINAL_SERVICE.txt').write_text(board('systemctl show rml24-integrated -p ActiveState -p NRestarts'));(p/'STATUS.json').write_text(json.dumps(dict(stage='COMPLETE_NOT_DEPLOYED',correct=result['correct'],denominator=96)));print('COMPLETE',result['correct'],96,flush=True)
except Exception as e:
 (p/'STATUS.json').write_text(json.dumps(dict(stage='FAILED_REQUIRES_REVIEW',error=str(e))));raise
