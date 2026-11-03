from pathlib import Path
import importlib.util,tempfile,json,subprocess,sys
root=Path(__file__).parent;sys.path.insert(0,str(root));spec=importlib.util.spec_from_file_location('installer_test',root/'install_release.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);real=subprocess.run;subprocess.run=lambda *a,**k:(_ for _ in ()).throw(AssertionError('no device/systemd/SD command permitted during invalid gate test'));passed=[]
try:
 with tempfile.TemporaryDirectory() as tmp:
  b=Path(tmp);extras=b/'extras';extras.mkdir();m.EXTRAS=extras;m.ROOT=b/'install';m.SOURCE=b/'missing_source'
  valid=dict(all_passed=True,fixed_correct=235,search_correct=235,sweep_correct=23,missing=0)
  for key,value in [('all_passed',False),('fixed_correct',234),('search_correct',234),('sweep_correct',22),('missing',1)]:
   data=dict(valid);data[key]=value;(extras/'RUNTIME_GATES.json').write_text(json.dumps(data))
   try:m.stage();raise RuntimeError('gate bypass')
   except AssertionError as exc:
    assert str(exc)!='no device/systemd/SD command permitted during invalid gate test'
   assert not m.ROOT.exists();passed.append(key)
  (extras/'RUNTIME_GATES.json').write_text(json.dumps(valid))
  try:m.stage();raise RuntimeError('missing source bypass')
  except FileNotFoundError:pass
  assert not m.ROOT.exists();passed.append('source_identity_before_writes')
  import deployment_launcher as launcher
  release=b/'release';release.mkdir();launcher.ROOT=release;(release/'PROMOTED_RELEASE.json').write_text(json.dumps(dict(all_promotion_gates_passed=False)))
  try:launcher.main();raise AssertionError('promotion bypass')
  except RuntimeError as exc:assert str(exc)=='release not promoted'
  passed.append('launcher_promotion_gate')
finally:subprocess.run=real
print(json.dumps(dict(passed=len(passed),tests=passed,device_access=False),indent=2))
