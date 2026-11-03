from pathlib import Path
import time,json,subprocess,sys,random,py_compile
src=Path(__file__).parent
for _ in range(500):
 if (src/'BANDWIDTH_WEAK_COVERAGE.json').exists():break
 time.sleep(5)
assert (src/'BANDWIDTH_WEAK_COVERAGE.json').exists();p=src.parent/'rml24_gainfreeze_range_paired_20261101';p.mkdir(exist_ok=False);plan=json.loads((src/'FROZEN_PLAN.json').read_text());cases=[dict(class_index=c,repeats=8,tx_gain_db=g) for c in range(24) for g in (-60,-40)];random.Random(110135).shuffle(cases);oldm=['gainfreeze_bw3','gainfreeze_bw5'];newm=['manual_bw5','gainfreeze_bw5'];plan.update(cases=cases,modes=newm,scope='same24classes x2powers x fixed35dB/frozenAGC,5MHz; both original and fallback scores retained');(p/'FROZEN_PLAN.json').write_text(json.dumps(plan,indent=2))
for name in ['capture_paired.py','run_paired.py','classify_paired.py','tx_paired.py','run_paired_validation.py','watch_and_score.py','run_and_evaluate.py']:
 s=(src/name).read_text().replace(src.name,p.name).replace(repr(oldm),repr(newm)).replace("(root/'gainfreeze_bw3',root/'gainfreeze_bw5')","(root/'manual_bw5',root/'gainfreeze_bw5')").replace('for gain in (-67.5,-70):','for gain in (-60,-40):').replace('BANDWIDTH_WEAK_COVERAGE.json','GAINFREEZE_PAIRED_COVERAGE.json')
 (p/name).write_text(s);py_compile.compile(str(p/name),doraise=True)
for name in ['capture_paired.py','run_paired.py','classify_paired.py']:
 subprocess.run(['powershell','-NoProfile','-File','E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/name),'-Remote','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/'+name],check=True)
time.sleep(5);subprocess.run([sys.executable,str(p/'run_and_evaluate.py')],stdout=(p/'chain.log').open('w'),stderr=subprocess.STDOUT,check=True);print('GAINFREEZE_RANGE_PAIRED_COMPLETE_NOT_DEPLOYED')
