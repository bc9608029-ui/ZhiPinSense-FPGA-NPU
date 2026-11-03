from pathlib import Path
import json,time,subprocess,sys,random,py_compile
p=Path(__file__).parent
for _ in range(360):
 if (p/'SCORE.json').exists():break
 time.sleep(5)
assert (p/'SCORE.json').exists();score=json.loads((p/'SCORE.json').read_text())[0];events=json.loads((p/'gainfreeze/VARIABLE_TX_EVENTS.json').read_text());one=sum(x['correct'] for x,e in zip(score['rows'],events) if e['repeats']==1);n=1 if one==24 else 8;dst=p.parent/'rml24_bandwidth_freeze_validation_20261101';dst.mkdir(exist_ok=False);modes=['gainfreeze_bw3','gainfreeze_bw5','gainfreeze_bw18'];cases=[dict(class_index=i,repeats=n) for i in range(24)];random.Random(110126).shuffle(cases);plan=json.loads((p/'FROZEN_PLAN.json').read_text());plan.update(cases=cases,modes=modes,denominator_per_mode=24,selected_repeats=n,scope='three bandwidth groups, gain settles then freezes; fixed24 per group');(dst/'FROZEN_PLAN.json').write_text(json.dumps(plan,indent=2))
for name in ['capture_paired.py','run_paired.py','classify_paired.py','tx_paired.py','run_paired_validation.py','watch_and_score.py']:
 s=(p/name).read_text().replace(p.name,dst.name).replace("['gainfreeze']",repr(modes)).replace("root/'gainfreeze/CAPTURE_RESULT.json'","root/'gainfreeze_bw18/CAPTURE_RESULT.json'").replace("(root/'gainfreeze',)","(root/'gainfreeze_bw3',root/'gainfreeze_bw5',root/'gainfreeze_bw18')").replace('time.monotonic()+235','time.monotonic()+120').replace('len(ev)==48','len(ev)==24').replace('denominator=48','denominator=24')
 if name=='capture_paired.py':s=s.replace("sys.argv[1]=='gainfreeze'","sys.argv[1].startswith('gainfreeze')").replace("[('manual',35,5000000)]","[('manual',35,int(sys.argv[1].split('bw')[1])*1000000)]")
 (dst/name).write_text(s);py_compile.compile(str(dst/name),doraise=True)
for name in ['capture_paired.py','run_paired.py','classify_paired.py']:
 subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(dst/name),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+name],check=True)
time.sleep(5);w=subprocess.Popen([sys.executable,str(dst/'watch_and_score.py')],stdout=(dst/'watch.log').open('w'),stderr=subprocess.STDOUT);subprocess.run([sys.executable,str(dst/'run_paired_validation.py')],stdout=(dst/'run.log').open('w'),stderr=subprocess.STDOUT,check=True);assert w.wait(timeout=1500)==0;print('BANDWIDTH_VALIDATION_COMPLETE_NOT_DEPLOYED')
