from pathlib import Path
import shutil,json,hashlib,subprocess
src=Path('/root/rml24_gainfreeze_integration_20261101/candidate');dst=Path('/root/rml24_gainfreeze_lockpilot_20261101/candidate');base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031')
assert not dst.exists();dst.parent.mkdir(exist_ok=True);shutil.copytree(src,dst);b=dst/'candidate/rml24_final/board_runtime';f=b/'standalone_receiver.py';original=f.read_text();oldsha=hashlib.sha256(f.read_bytes()).hexdigest()
needle="                        d=detect_public_training(candidate,public.train)\n                        ok=d.score>=.10 and abs(d.coarse_cfo_hz)<=1000"
replacement="""                        d=detect_public_training(candidate,public.train)
                        primary=d
                        fallback_used=False
                        if not (d.score>=.10 and abs(d.coarse_cfo_hz)<=1000):
                            from locked_detector import detect_locked
                            alternative=detect_locked(candidate,public.train)
                            if alternative['score']>=.10 and abs(alternative['coarse_cfo_hz'])<=1000:
                                d=type(d)(**alternative)
                                fallback_used=True
                        ok=d.score>=.10 and abs(d.coarse_cfo_hz)<=1000"""
assert original.count(needle)==1;new=original.replace(needle,replacement)
needle2="                                          cfo_hz=d.coarse_cfo_hz,locked_check=True,accepted=ok))"
replacement2="                                          cfo_hz=d.coarse_cfo_hz,locked_check=True,accepted=ok,locked_fallback_used=fallback_used,primary_public_score=primary.score,primary_cfo_hz=primary.coarse_cfo_hz))"
assert new.count(needle2)==1;f.write_text(new.replace(needle2,replacement2));shutil.copyfile(base/'locked_detector.py',b/'locked_detector.py');newsha=hashlib.sha256(f.read_bytes()).hexdigest();w=b/'receiver_repeat_mean_gapfix1.py';s=w.read_text();assert oldsha in s;w.write_text(s.replace(oldsha,newsha));identity=dst/'evidence/CANDIDATE_SOURCE_IDENTITY.json';d=json.loads(identity.read_text())
for item in (f,w,b/'locked_detector.py'):d[str(item.relative_to(dst))]=hashlib.sha256(item.read_bytes()).hexdigest()
identity.write_text(json.dumps(d,indent=2));receipt=dst/'PROMOTED_RELEASE.json';r=json.loads(receipt.read_text());r['all_promotion_gates_passed']=False;r['promotion_scope']='LOCKED_FALLBACK_STAGED_NOT_RF_TESTED_NOT_DEPLOYED'
for item in (f,w,b/'locked_detector.py',identity):r['files'][str(item.relative_to(dst))]=hashlib.sha256(item.read_bytes()).hexdigest()
receipt.write_text(json.dumps(r,indent=2));py='/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3';subprocess.run([py,'-m','py_compile',str(f),str(w),str(b/'locked_detector.py')],check=True);subprocess.run([py,'-c','import sys;sys.path.insert(0,'+repr(str(b))+');import receiver_repeat_mean_gapfix1 as m;m.verify_base();print("LOCKED_INNER_DEPENDENCIES_PASS")'],check=True)
result=dict(state='STAGED_COMPILED_NOT_RF_TESTED_NOT_DEPLOYED',root=str(dst),formal_current=str(Path('/opt/rml24-integrated/current').resolve()),changes='Already-locked branch only; primary rejection may use public centered correlation; original score/CFO logged; strict existing recovery and NPU unchanged',old_standalone_sha256=oldsha,new_standalone_sha256=newsha,identity=d);(dst.parent/'STAGING_RESULT.json').write_text(json.dumps(result,indent=2));print('LOCKED_CANDIDATE_STAGED_NO_AUTOSTART_CHANGE',flush=True)
