from pathlib import Path
import hashlib,json,tarfile,shutil,subprocess
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');archive=base/'ui_patch.tar.gz';assert hashlib.sha256(archive.read_bytes()).hexdigest()=='3881f2feb4048797a14d0da2b217c3d3da1f4299218c7122548bad9762c43b7e'
incoming=base/'ui_timing_patch';incoming.mkdir(exist_ok=False)
expected={'candidate/ui_sw/signal_history.hpp','candidate/ui_sw/ui_render.cpp','candidate/board_package/board_ui_live_rml24_final.cpp','PATCH_IDENTITY.json','tests/test_history_ui.cpp'}
with tarfile.open(archive) as t:
 assert set(t.getnames())==expected and all(x.isfile() for x in t.getmembers());t.extractall(incoming)
old=Path('/root/rml24_fpga_ui_20261031/delivery_guard_persistent');root=old.parent/'delivery_ui_timing';shutil.copytree(old,root);changes=[]
for rel,identity in json.loads((incoming/'PATCH_IDENTITY.json').read_text()).items():
 p=root/rel;before=hashlib.sha256(p.read_bytes()).hexdigest();assert before in [identity['before'],identity.get('accepted_tested_before')],(rel,before)
 assert hashlib.sha256((incoming/rel).read_bytes()).hexdigest()==identity['after'];shutil.copyfile(incoming/rel,p);changes.append(dict(file=rel,before=before,after=identity['after']))
p=root/'candidate/rml24_final/board_runtime/standalone_receiver.py';before=hashlib.sha256(p.read_bytes()).hexdigest();assert before=='4f30870996ba62a5347f23ae627874fc79c4a0aefe23f270d3cafe0568c9d75f';s=p.read_text();assert s.count('capture_ns=time.time_ns()')>=2;s=s.replace('args=args_parse();out=',"args=args_parse();boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip();out=");s=s.replace('capture_ns=0','capture_ns=0;capture_mono_ns=0');s=s.replace('capture_ns=time.time_ns()','capture_ns=time.time_ns();capture_mono_ns=time.monotonic_ns()');needle='capture_time_ns=capture_ns,';assert needle in s;s=s.replace(needle,"capture_time_ns=capture_ns,capture_monotonic_ns=capture_mono_ns,clock_id='board-monotonic-v1',boot_id=boot_id,");compile(s,str(p),'exec');p.write_text(s);after=hashlib.sha256(p.read_bytes()).hexdigest();changes.append(dict(file=str(p.relative_to(root)),before=before,after=after))
p=root/'candidate/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py';s=p.read_text();assert before in s;s=s.replace(before,after);p.write_text(s);changes.append(dict(file=str(p.relative_to(root)),after=hashlib.sha256(p.read_bytes()).hexdigest()))
(root/'tests').mkdir(exist_ok=True);shutil.copyfile(incoming/'tests/test_history_ui.cpp',root/'tests/test_history_ui.cpp')
with (root/'ui_build.log').open('w') as f:subprocess.run(['bash',str(root/'candidate/board_package/build_ui_live_rml24_final.sh')],stdout=f,stderr=subprocess.STDOUT,check=True)
cpp=[root/'tests/test_history_ui.cpp']+[root/'candidate/ui_sw'/name for name in ['font_atlas.cpp','font_atlas_data.cpp','ui_render.cpp','waterfall_render.cpp']]
with (root/'ui_test_build.log').open('w') as f:subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror']+list(map(str,cpp))+['-o',str(root/'test_history_ui')],stdout=f,stderr=subprocess.STDOUT,check=True)
with (root/'ui_test.log').open('w') as f:subprocess.run([str(root/'test_history_ui')],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
identity_path=root/'evidence/CANDIDATE_SOURCE_IDENTITY.json';identity=json.loads(identity_path.read_text())
for change in changes:identity[change['file']]=hashlib.sha256((root/change['file']).read_bytes()).hexdigest()
identity['candidate/bin/board_ui_live_rml24_final']=hashlib.sha256((root/'candidate/bin/board_ui_live_rml24_final').read_bytes()).hexdigest();identity_path.write_text(json.dumps(identity,indent=2))
receipt=dict(status='BOARD_BUILD_AND_HISTORY_TEST_PASS_RF_SHORT_PENDING',changes=changes,ui_binary_sha=identity['candidate/bin/board_ui_live_rml24_final'],receiver_sha=after,model_changed=False,rf_algorithm_changed=False,bit_changed=False,official_service_changed=False)
(root/'evidence/UI_TIMING_UPDATE.json').write_text(json.dumps(receipt,indent=2));print('BOARD_UI_TIMING_BUILD_PASS '+json.dumps(receipt),flush=True)
