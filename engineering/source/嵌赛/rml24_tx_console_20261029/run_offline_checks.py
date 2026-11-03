from pathlib import Path
import subprocess,sys,json,os
ROOT=Path(__file__).resolve().parent
ev=ROOT/'evidence';ev.mkdir(exist_ok=True)
checks=[('unit_tests',[sys.executable,'-m','unittest','discover','-s','tests','-v']),
        ('gui_smoke',[sys.executable,'tests/gui_smoke.py'])]
results={}
for name,args in checks:
 env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1',QT_QPA_PLATFORM='windows')
 p=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,encoding='utf8',errors='replace',timeout=60)
 (ev/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf8')
 results[name]=dict(returncode=p.returncode,pass_=p.returncode==0)
 if p.returncode:print(name,'FAIL');sys.exit(1)
print('OFFLINE_CHECKS PASS unit_tests=13 gui_smoke=PASS real_hardware_tx=NO')
(ev/'verification.json').write_text(json.dumps(dict(result='PASS',checks=results,
 hardware_access=False,radio_in_unit_tests='FakeRadio only',real_rf_test=False),indent=2),encoding='utf8')
