from pathlib import Path
import hashlib,json,shutil,tarfile,subprocess
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');archive=base/'visual_patch.tar.gz';assert hashlib.sha256(archive.read_bytes()).hexdigest()=='a55703478f9ffed2f5378a511e031104e5400c4f93d4498b290e12c27de77e03'
incoming=base/'visual_patch';incoming.mkdir(exist_ok=False)
with tarfile.open(archive) as t:
 assert set(t.getnames())=={'candidate/ui_sw/waterfall_render.cpp','candidate/ui_sw/ui_render.cpp','tests/test_visual.cpp','VISUAL_PATCH.json'} and all(x.isfile() for x in t.getmembers());t.extractall(incoming)
old=Path('/root/rml24_fpga_ui_20261031/delivery_release_candidate');root=old.parent/'delivery_deploy_final';shutil.copytree(old,root);patch=json.loads((incoming/'VISUAL_PATCH.json').read_text())
for x in patch['changes']:
 assert hashlib.sha256((root/x['file']).read_bytes()).hexdigest()==x['before'];assert hashlib.sha256((incoming/x['file']).read_bytes()).hexdigest()==x['after'];shutil.copyfile(incoming/x['file'],root/x['file'])
shutil.copyfile(incoming/'tests/test_visual.cpp',root/'tests/test_visual.cpp')
with (root/'visual_ui_build.log').open('w') as f:subprocess.run(['bash',str(root/'candidate/board_package/build_ui_live_rml24_final.sh')],stdout=f,stderr=subprocess.STDOUT,check=True)
cpp=[root/'tests/test_visual.cpp']+[root/'candidate/ui_sw'/n for n in ('font_atlas.cpp','font_atlas_data.cpp','ui_render.cpp')]
with (root/'visual_test_build.log').open('w') as f:subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror']+list(map(str,cpp))+['-o',str(root/'test_visual')],stdout=f,stderr=subprocess.STDOUT,check=True)
with (root/'visual_test.log').open('w') as f:subprocess.run([str(root/'test_visual')],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
p=root/'evidence/CANDIDATE_SOURCE_IDENTITY.json';identity=json.loads(p.read_text())
for x in patch['changes']:identity[x['file']]=x['after']
identity['candidate/bin/board_ui_live_rml24_final']=hashlib.sha256((root/'candidate/bin/board_ui_live_rml24_final').read_bytes()).hexdigest();p.write_text(json.dumps(identity,indent=2));receipt=dict(status='VISUAL_BUILD_PIXEL_TEST_PASS_PHYSICAL_PENDING',ui_sha=identity['candidate/bin/board_ui_live_rml24_final'],changes=patch['changes'],receiver_changed=False,model_changed=False,fft_math_changed=False);(root/'evidence/VISUAL_FINAL_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print('FINAL_VISUAL_PASS '+json.dumps(receipt),flush=True)
