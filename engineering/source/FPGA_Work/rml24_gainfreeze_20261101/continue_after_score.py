from pathlib import Path
import time,json,subprocess,sys,random,py_compile
p=Path(__file__).parent
for _ in range(400):
 f=p/'SCORE.json'
 if f.exists():break
 state=json.loads((p/'STATUS.json').read_text()) if (p/'STATUS.json').exists() else {}
 if state.get('stage')=='FAILED':raise RuntimeError(state)
 time.sleep(5)
assert f.exists();scores=json.loads(f.read_text());a={x['mode']:x['correct'] for x in scores};chosen='gainfreeze' if a['gainfreeze']>=a['manual'] else 'manual';dst=p.parent/'rml24_reduced_repeat_followup_20261101';assert not dst.exists();dst.mkdir();cases=[dict(class_index=c,repeats=n) for c in range(24) for n in (1,8)];random.Random(110125).shuffle(cases);plan=json.loads((p/'FROZEN_PLAN.json').read_text());plan.update(cases=cases,modes=[chosen],denominator_per_mode=48,selection_rule='gainfreeze only if paired score at least manual; otherwise manual');(dst/'FROZEN_PLAN.json').write_text(json.dumps(plan,indent=2));(p/'NEXT_STAGE_SELECTION.json').write_text(json.dumps(dict(scores=a,chosen=chosen,next=str(dst)),indent=2))
for name in ['capture_paired.py','run_paired.py','classify_paired.py','tx_paired.py','run_paired_validation.py','watch_and_score.py']:
 t=(p/name).read_text().replace('rml24_gainfreeze_20261101',dst.name).replace("['manual','gainfreeze']",repr([chosen])).replace("root/'gainfreeze/CAPTURE_RESULT.json'","root/"+repr(chosen+"/CAPTURE_RESULT.json")).replace("(root/'manual',root/'gainfreeze')","(root/"+repr(chosen)+",)").replace('time.monotonic()+120','time.monotonic()+235').replace('len(ev)==24','len(ev)==48').replace('denominator=24','denominator=48').replace('range(200)','range(400)')
 (dst/name).write_text(t);py_compile.compile(str(dst/name),doraise=True)
for name in ['capture_paired.py','run_paired.py','classify_paired.py']:
 subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(dst/name),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+name],check=True)
time.sleep(5);watch=subprocess.Popen([sys.executable,str(dst/'watch_and_score.py')],stdout=(dst/'watch.log').open('w'),stderr=subprocess.STDOUT);subprocess.run([sys.executable,str(dst/'run_paired_validation.py')],check=True,stdout=(dst/'run.log').open('w'),stderr=subprocess.STDOUT);assert watch.wait(timeout=1200)==0
results=json.loads((dst/'SCORE.json').read_text());(dst/'AUTOMATIC_CHAIN_COMPLETE.json').write_text(json.dumps(dict(previous=str(p),selected_mode=chosen,results=results,deploy=False),indent=2));print('FOLLOWUP_COMPLETED_NOT_DEPLOYED',flush=True)
