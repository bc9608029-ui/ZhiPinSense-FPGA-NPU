from pathlib import Path
import shutil,hashlib,json
old=Path('/root/rml24_fpga_ui_20261031/delivery_shared');root=old.parent/'delivery_guard';shutil.copytree(old,root)
g=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/hardware_restart_guard.py');dest=root/'scripts/hardware_restart_guard.py';shutil.copyfile(g,dest)
p=root/'scripts/run_candidate_finalize_v2.py';s=p.read_text();needle="npu=spawn('npu',[Path('/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared'),"
replacement="npu=spawn('npu',[sys.executable,ROOT/'scripts/hardware_restart_guard.py','--state-dir','/run/rml24-fpga-shared-guard',Path('/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared'),"
assert needle in s;s=s.replace(needle,replacement)
needle="        result['stop_errors']=stop_children(children)";assert needle in s
s=s.replace(needle,needle+"\n        if any(role=='npu' and child.poll()==78 for role,child in children):\n            result['hardware_reset_required']=True;result['error']='Hardware guard blocked restart; full board reboot required'")
needle="    return 0 if result['clean_stop'] else 1";assert needle in s;s=s.replace(needle,"    return 78 if result.get('hardware_reset_required') else (0 if result['clean_stop'] else 1)")
p.write_text(s)
identity=root/'evidence/CANDIDATE_SOURCE_IDENTITY.json';v=json.loads(identity.read_text());v['scripts/hardware_restart_guard.py']=hashlib.sha256(dest.read_bytes()).hexdigest()
if 'scripts/run_candidate_finalize_v2.py' in v:v['scripts/run_candidate_finalize_v2.py']=hashlib.sha256(p.read_bytes()).hexdigest()
identity.write_text(json.dumps(v,indent=2));compile(s,str(p),'exec');compile(dest.read_text(),str(dest),'exec')
(root/'evidence/RESTART_GUARD_FREEZE.json').write_text(json.dumps(dict(guard_sha=hashlib.sha256(dest.read_bytes()).hexdigest(),supervisor_sha=hashlib.sha256(p.read_bytes()).hexdigest(),base_unchanged=str(old),worker_unchanged=True,model_unchanged=True,bit_unchanged=True,formal_service_unchanged=True),indent=2))
print('INDEPENDENT_GUARD_CANDIDATE_PREPARED')
