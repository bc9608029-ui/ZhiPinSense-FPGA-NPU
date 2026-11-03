from pathlib import Path
import shutil,json,hashlib
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=Path('/root/rml24_three_modes_execution_20261029/delivery_progressfix1');stage=old.parent/'fpga_ui_integration_20261031';root=Path('/root/rml24_fpga_ui_20261031');root.mkdir(exist_ok=False);new=root/'delivery'
assert sha(old/'candidate/rml24_final/board_runtime/standalone_receiver.py')=='ee8c484d33a631f2a1cac67a15f2c1347d39e0e87efb65390112969b873601f0'
shutil.copytree(old,new)
base=new/'candidate/rml24_final'
for name,sub in [('standalone_receiver.py','board_runtime'),('ui_event.py','runtime'),('spectrum_backend.py','runtime')]:shutil.copyfile(stage/name,base/sub/name)
p=base/'board_runtime/receiver_repeat_mean_gapfix1.py';s=p.read_text();s=s.replace('ee8c484d33a631f2a1cac67a15f2c1347d39e0e87efb65390112969b873601f0',sha(base/'board_runtime/standalone_receiver.py'));p.write_text(s)
p=new/'scripts/run_candidate_finalize_v2.py';s=p.read_text();needle="    if a.save_captures:cmd.append('--save-captures')";assert needle in s;s=s.replace(needle,"    cmd += ['--spectrum-backend','fpga','--spectrum-driver','/root/rml24_fpga_diag_1793380588/scan_xrt']\n"+needle);p.write_text(s)
p=new/'evidence/CANDIDATE_SOURCE_IDENTITY.json';identity=json.loads(p.read_text());changes={}
for x in [base/'board_runtime/standalone_receiver.py',base/'board_runtime/receiver_repeat_mean_gapfix1.py',base/'runtime/ui_event.py',base/'runtime/spectrum_backend.py',new/'scripts/run_candidate_finalize_v2.py']:
 rel=str(x.relative_to(new));changes[rel]=dict(before=identity.get(rel),after=sha(x));identity[rel]=sha(x);compile(x.read_text(),str(x),'exec')
p.write_text(json.dumps(identity,indent=2));(root/'INDEPENDENT_CANDIDATE_FREEZE.json').write_text(json.dumps(dict(changes=changes,scope='display PSD only; CPU detection, model, recovery unchanged',original_preserved=True),indent=2));print('INDEPENDENT_UI_FPGA_CANDIDATE_READY')
