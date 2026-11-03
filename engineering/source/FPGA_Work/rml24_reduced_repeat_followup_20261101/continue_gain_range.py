from pathlib import Path
import json,time,subprocess,sys,random,py_compile
parent=Path(__file__).parent.parent;p=parent/'rml24_bandwidth_freeze_validation_20261101'
for _ in range(1000):
 if (p/'SCORE.json').exists():break
 time.sleep(5)
assert (p/'SCORE.json').exists();scores=json.loads((p/'SCORE.json').read_text());winner=max(scores,key=lambda x:(x['correct'],x['mode']=='gainfreeze_bw5'));mode=winner['mode'];dst=parent/'rml24_gain_range_validation_20261101';dst.mkdir(exist_ok=False);plan=json.loads((p/'FROZEN_PLAN.json').read_text());n=plan['selected_repeats'];cases=[dict(class_index=c,repeats=n,tx_gain_db=g) for c in range(24) for g in (-70,-60,-50,-40,-30)];random.Random(110127).shuffle(cases);plan.update(cases=cases,modes=[mode],denominator_per_mode=120,scope='24classes x5 TX gain settings; diagnostic only, not calibrated dBm');(dst/'FROZEN_PLAN.json').write_text(json.dumps(plan,indent=2));(dst/'PREVIOUS_BANDWIDTH_SCORES.json').write_text(json.dumps(scores,indent=2))
oldmodes=['gainfreeze_bw3','gainfreeze_bw5','gainfreeze_bw18']
for name in ['capture_paired.py','run_paired.py','classify_paired.py','tx_paired.py','run_paired_validation.py','watch_and_score.py']:
 t=(p/name).read_text().replace(p.name,dst.name).replace(repr(oldmodes),repr([mode])).replace("root/'gainfreeze_bw18/CAPTURE_RESULT.json'","root/"+repr(mode+'/CAPTURE_RESULT.json')).replace("(root/'gainfreeze_bw3',root/'gainfreeze_bw5',root/'gainfreeze_bw18')","(root/"+repr(mode)+",)").replace('time.monotonic()+120','time.monotonic()+535').replace('range(300)','range(2000)').replace('len(ev)==24','len(ev)==120').replace('denominator=24','denominator=120')
 if name=='tx_paired.py':
  t=t.replace("n=case['repeats'];item=", "r.set(r.tx,'hardwaregain',case['tx_gain_db']);actual_gain=float(r.get(r.tx,'hardwaregain').split()[0]);assert abs(actual_gain-case['tx_gain_db'])<.01;\n  n=case['repeats'];item=").replace("e=dict(class_index=case['class_index'],", "e=dict(tx_gain_db=case['tx_gain_db'],class_index=case['class_index'],")
 if name=='capture_paired.py':t=t.replace('import sys,json,time,numpy as np','import sys,json,time,numpy as np,shutil').replace('u=link.scan_usb();','assert shutil.disk_usage(root).free>800*1024*1024;u=link.scan_usb();')
 (dst/name).write_text(t);py_compile.compile(str(dst/name),doraise=True)
for name in ['capture_paired.py','run_paired.py','classify_paired.py']:
 subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(dst/name),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+name],check=True)
time.sleep(5);w=subprocess.Popen([sys.executable,str(dst/'watch_and_score.py')],stdout=(dst/'watch.log').open('w'),stderr=subprocess.STDOUT);subprocess.run([sys.executable,str(dst/'run_paired_validation.py')],stdout=(dst/'run.log').open('w'),stderr=subprocess.STDOUT,check=True);assert w.wait(timeout=2000)==0
score=json.loads((dst/'SCORE.json').read_text())[0];events=json.loads((dst/mode/'VARIABLE_TX_EVENTS.json').read_text());out=[]
for gain in (-70,-60,-50,-40,-30):
 r=[s for s,e in zip(score['rows'],events) if e['tx_gain_db']==gain];out.append(dict(tx_gain_db=gain,denominator=24,correct=sum(x['correct'] for x in r),missing=sum(x['chosen'] is None for x in r)))
(dst/'GAIN_COVERAGE.json').write_text(json.dumps(out,indent=2));print('GAIN_COVERAGE_COMPLETE_NOT_DEPLOYED',flush=True)
