from pathlib import Path
import json,time,subprocess,re,gzip,base64,hashlib
p=Path(__file__).parent;ui=p.parent/'rf_smoke';bounded=Path('E:/FPGA_Work/rml24_sweep_boundednorm_rf_20261102');old=Path('E:/FPGA_Work/rml24_gain_headroom_centerfix_autonomy_20261101')
def read(f):return json.loads(Path(f).read_text(encoding='utf-8'))
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def ps(args):
 q=subprocess.run(['powershell','-NoProfile','-File']+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert q.returncode==0,q.stdout[-1500:];return q.stdout.decode('utf-8',errors='replace')
def board(cmd,seconds=4):return ps(['E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101/serial_exclusive.ps1','-Command',cmd,'-Seconds',str(seconds)])
for _ in range(150):
 try:state=read(ui/'STATUS.json')
 except Exception:state={}
 if state.get('stage')=='UI_GAIN_SMOKES_PASS_WAIT_SCREEN':break
 if state.get('stage','').startswith(('RF_GATE_FAILED','STOPPED_REVIEW')):raise RuntimeError(state)
 time.sleep(5)
else:raise RuntimeError('UI smoke did not finish; no device access')
time.sleep(3);u=read(ui/'RESULTS.json');b=read(bounded/'RESULTS.json');o=read(old/'RESULTS.json');assert len(u)==3 and all(x['gate_pass'] and x['missing']==0 for x in u);assert len(b)==4 and all(x['gate_pass'] and x['missing']==0 for x in b)
base='/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031';remote='/root/rml24_gain_ui_sync_20261102';(p/'HELPER_UPLOAD.txt').write_text(ps(['E:/rml24_three_modes_execution_20261029/upload.ps1','-Local',str(p/'software_deploy_gain_ui.py'),'-Remote',base+'/software_deploy_gain_ui.py']),encoding='utf-8');(p/'SCOPE_ACTION.txt').write_text(board('python3 '+base+'/software_deploy_gain_ui.py scope',8),encoding='utf-8')
code='import pathlib,gzip,base64; p=pathlib.Path("'+remote+'/scope_DONE.json");print("SCOPE_BEGIN"+base64.b64encode(gzip.compress(p.read_bytes())).decode()+"SCOPE_END")';import shlex;text=board('python3 -c '+shlex.quote(code),4);(p/'SCOPE_EXPORT.txt').write_text(text,encoding='utf-8');m=re.search(r'SCOPE_BEGIN([A-Za-z0-9+/=\s]+)SCOPE_END',text);assert m,text[-1000:];scope=json.loads(gzip.decompress(base64.b64decode(re.sub(r'\s','',m[1]))));assert scope['sweep_scope']['old_identity']=='bf43d2c52a3d06831496e76d51b7acff7505dc2edb64871008a1043af718a753' and scope['display_scope']['new_identity']=='d960b668f1298962ec230db661fbcf2f7881206ba49c1ceb4d39dc25518c611b';(p/'SCOPE_PROOF.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')
formal=[]
for name in ('fixed240','search240','wide13'):
 r=next(x for x in o if x['name']==name);assert r['gate_pass'] and r['missing']==0;formal.append(dict(r,evidence_provenance='Inherited unchanged mode after exact two-stage source equivalence',evidence_directory=str(old/name),score_sha256=sha(old/name/'SCORE.json')))
r=next(x for x in b if x['name']=='sweep24');formal.append(dict(r,evidence_provenance='New sweep-only correction RF; display-only equivalence to final candidate',evidence_directory=str(bounded/'sweep24'),score_sha256=sha(bounded/'sweep24/SCORE.json')))
smokes=[x for x in b if x['name']!='sweep24'];gates=dict(all_passed=True,candidate_identity_sha256=scope['display_scope']['new_identity'],model_public_bit_unchanged=True,results=formal,smokes=smokes,ui_smokes=u,scope_equivalence=scope,scope_proof_sha256=sha(p/'SCOPE_PROOF.json'),replaced_failed_sweep_reference=dict(correct=22,denominator=24,source_results_sha256=sha(old/'RESULTS.json'),evidence_retained=True),scope='Frozen240-waveform system, original8 repeats/2.56MS/s; not unseen signal or arbitrary amplitude guarantee',new_full_fixed_search_regressions_claimed=False)
(p/'QUALIFIED_GATES.json').write_text(json.dumps(gates,indent=2),encoding='utf-8');assert not (p/'DEPLOYMENT_USER_READY.json').exists();ready=dict(status='READY_FOR_USER_SCREEN_CONFIRMATION_NOT_DEPLOYED',candidate_identity_sha256=gates['candidate_identity_sha256'],scope_proof_verified=True,software_helper_uploaded_but_scope_action_only=True,model_bit_frame_unchanged=True,qualification_sha256=sha(p/'QUALIFIED_GATES.json'),screen_confirmation_required=True);(p/'READY_FOR_SCREEN.json').write_text(json.dumps(ready,indent=2),encoding='utf-8');print('PREDEPLOY_AUDIT_PASS_WAIT_USER_SCREEN',flush=True)
