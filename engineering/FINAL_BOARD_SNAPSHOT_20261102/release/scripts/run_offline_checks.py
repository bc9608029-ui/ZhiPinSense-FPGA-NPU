from pathlib import Path
import ast,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
results={}
for name in ['test_sweep.py','test_receiver_integration.py','test_supervisor.py']:
    p=subprocess.run([sys.executable,'-I',str(ROOT/'tests'/name)],cwd=ROOT,capture_output=True,text=True,errors='replace')
    (ROOT/'evidence'/name.replace('.py','.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
    results[name]=p.returncode;print(name,p.returncode)
    if p.returncode:raise SystemExit(p.stdout+p.stderr)
paths=list((ROOT/'candidate/rml24_final').rglob('*.py'))+[ROOT/'scripts/run_candidate.py']
for path in paths:ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,8))
results['python38_syntax_files']=len(paths)
(ROOT/'evidence/python_checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('OFFLINE_PYTHON_PASS (no device; Python3.8 syntax only, not Python3.8 runtime)')
