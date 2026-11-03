from pathlib import Path
import json,hashlib,shutil,subprocess
source=Path('/root/rml24_gain_headroom_integration_20261101/candidate');dst=Path('/root/rml24_gain_headroom_centerfix_20261101/candidate');assert not dst.exists();dst.parent.mkdir(exist_ok=True);shutil.copytree(source,dst);b=dst/'candidate/rml24_final/board_runtime';runtime=dst/'candidate/rml24_final/runtime';receiver=b/'standalone_receiver.py';oldsha=hashlib.sha256(receiver.read_bytes()).hexdigest();text=receiver.read_text();anchor='                    raw,center,capture_ns,step=sweep.probe(';assert text.count(anchor)==1
callback="""                    def confirm_centred(z):
                        primary=detect_public_training(z,public.train)
                        if primary.score>=.10 and abs(primary.coarse_cfo_hz)<=1000:return primary
                        from locked_detector import detect_locked
                        from types import SimpleNamespace
                        alternative=detect_locked(z,public.train)
                        if alternative['score']>=.10 and abs(alternative['coarse_cfo_hz'])<=1000:
                            return SimpleNamespace(**alternative,fallback_used=True,primary_score=primary.score,primary_cfo_hz=primary.coarse_cfo_hz)
                        return primary
""";text=text.replace(anchor,callback+anchor);needle="                        s['start_hz'],s['stop_hz'])";assert text.count(needle)==1;text=text.replace(needle,"                        s['start_hz'],s['stop_hz'],centred_detect=confirm_centred)");receiver.write_text(text)
f=runtime/'continuous_sweep.py';text=f.read_text();assert text.count('centred_cfo_limit=1000):')==1;text=text.replace('centred_cfo_limit=1000):','centred_cfo_limit=1000, centred_detect=None):');assert text.count('confirm = detect(raw)')==1;text=text.replace('confirm = detect(raw)','confirm = (centred_detect or detect)(raw)');needle='        step.update(confirmed_lo_hz=actual,';assert text.count(needle)==1;text=text.replace(needle,"        step.update(centred_fallback_used=bool(getattr(confirm,'fallback_used',False)),primary_confirmed_score=float(getattr(confirm,'primary_score',confirm.score)),primary_confirmed_cfo_hz=float(getattr(confirm,'primary_cfo_hz',confirm.coarse_cfo_hz)))\n"+needle);f.write_text(text)
w=b/'receiver_repeat_mean_gapfix1.py';text=w.read_text();assert oldsha in text;w.write_text(text.replace(oldsha,hashlib.sha256(receiver.read_bytes()).hexdigest()));identity=dst/'evidence/CANDIDATE_SOURCE_IDENTITY.json';d=json.loads(identity.read_text())
for item in (receiver,f,w):d[str(item.relative_to(dst))]=hashlib.sha256(item.read_bytes()).hexdigest()
identity.write_text(json.dumps(d,indent=2));receipt=dst/'PROMOTED_RELEASE.json';r=json.loads(receipt.read_text());r['all_promotion_gates_passed']=False;r['promotion_scope']='Gain headroom plus centred-confirmation fallback; original discovery/gates/model/framing unchanged; RF qualification pending'
for item in (receiver,f,w,identity):r['files'][str(item.relative_to(dst))]=hashlib.sha256(item.read_bytes()).hexdigest()
receipt.write_text(json.dumps(r,indent=2));py='/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3';subprocess.run([py,'-m','py_compile',str(receiver),str(f),str(w)],check=True);subprocess.run([py,'-c','import sys;sys.path.insert(0,'+repr(str(b))+');import receiver_repeat_mean_gapfix1 as m;m.verify_base();print("CENTREFIX_INNER_FROZEN_DEPS_PASS")'],check=True);(dst.parent/'STAGING_RESULT.json').write_text(json.dumps(dict(state='STAGED_NOT_DEPLOYED',root=str(dst),source=str(source),identity=d),indent=2));print('CENTREFIX_STAGED_NOT_DEPLOYED',flush=True)
