from pathlib import Path
import argparse,json,hashlib,os,shutil,subprocess,time,re,gzip,base64,collections
ROOT=Path('/root/rml24_gain_headroom_integration_20261101');SOURCE=ROOT/'candidate';BASE=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');CURRENT=Path('/opt/rml24-integrated/current');RELEASE=Path('/opt/rml24-integrated/releases/gain_headroom_20261101');UNIT=Path('/etc/systemd/system/rml24-integrated.service');MARKER=Path('/var/lib/rml24-fpga-shared-guard/reset_required.json');PY='/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def save(f,v):
 f=Path(f);tmp=f.with_name(f.name+'.tmp')
 with tmp.open('w') as h:json.dump(v,h,indent=2);h.flush();os.fsync(h.fileno())
 os.replace(str(tmp),str(f))
def run(argv):return subprocess.run(list(map(str,argv)),check=True)
def health():
 try:
  pid=int(subprocess.check_output(['systemctl','show','rml24-integrated','-p','MainPID','--value']).strip());args=Path('/proc/%d/cmdline'%pid).read_bytes().decode().strip('\0').split('\0');r=Path(args[args.index('--run')+1]);children=json.loads((r/'children.json').read_text());alive={c['role']:Path('/proc/%d/cmdline'%c['pid']).exists() and Path('/proc/%d/cmdline'%c['pid']).read_bytes().decode().strip('\0').split('\0')==list(map(str,c['argv'])) for c in children};ready=all(alive.get(k) for k in ('npu','ui','rx')) and all(token in (r/(k+'.log')).read_text(errors='replace') for k,token in [('npu','NPU_STREAM_READY'),('ui','UI_FB_READY'),('rx','STANDALONE_READY')]);return dict(ready=ready,run=str(r),alive=alive,release=str(CURRENT.resolve()))
 except Exception as e:return dict(ready=False,error=str(e),release=str(CURRENT.resolve()))
def wait_health(expected):
 for _ in range(60):
  h=health()
  if h.get('ready') and h.get('release')==str(expected):return h
  time.sleep(.5)
 raise RuntimeError('service health not ready '+json.dumps(h))
def stop_clean():
 run(['systemctl','stop','rml24-integrated'])
 for cmd in [['pgrep','-x','npu_stream'],['pgrep','-f','^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared']]:assert subprocess.run(cmd,stdout=subprocess.PIPE).returncode==1,'NPU owner remains'
 assert not MARKER.exists(),'dirty hardware guard; never force restart'
def switch(target):
 target=Path(target);assert target.is_dir();temp=CURRENT.with_name('current.next_headroom');assert not temp.exists() and not temp.is_symlink();os.symlink(str(target),str(temp));os.replace(str(temp),str(CURRENT));run(['sync'])
def stage():
 gates=json.loads((BASE/'HEADROOM_QUALIFIED_GATES.json').read_text());assert gates['all_passed'] and gates['model_public_bit_unchanged'];required={'fixed240':(240,235),'search240':(240,237),'sweep24':(24,24),'wide13':(13,13)};assert set(x['name'] for x in gates['results'])==set(required)
 for x in gates['results']:
  denominator,minimum=required[x['name']];assert x['denominator']==denominator and x['correct']>=minimum and x['missing']==0 and x['gate_pass']
 assert len(gates['smokes'])==2 and all(x['gate_pass'] and x['missing']==0 for x in gates['smokes']);assert sha(SOURCE/'evidence/CANDIDATE_SOURCE_IDENTITY.json')==gates['candidate_identity_sha256'];assert not RELEASE.exists();assert CURRENT.is_symlink() and health()['ready'];assert shutil.disk_usage('/').free>int(1.05*1024**3)
 expected=json.loads((SOURCE/'evidence/CANDIDATE_SOURCE_IDENTITY.json').read_text())
 for f,digest in expected.items():assert sha(SOURCE/f)==digest,f
 old=CURRENT.resolve();receipt=json.loads((SOURCE/'PROMOTED_RELEASE.json').read_text());assert receipt['boot']['candidate_bit_sha256']=='f42dd12f03bf81c65978b7034b45808efd5035f6a358cc54710f2404530a057c';assert 'rml24_pl_sha256='+receipt['boot']['candidate_bit_sha256'] in Path('/proc/cmdline').read_text().split();previous=dict(release=str(old),service_sha256=sha(UNIT),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),enabled=subprocess.check_output(['systemctl','is-enabled','rml24-integrated']).decode().strip());assert previous['enabled']=='enabled';save(ROOT/'DEPLOYMENT_PREVIOUS.json',previous);shutil.copytree(SOURCE,RELEASE);shutil.copyfile(BASE/'HEADROOM_QUALIFIED_GATES.json',RELEASE/'evidence/GAIN_QUALIFIED_GATES.json');receipt['all_promotion_gates_passed']=True;receipt['promotion_scope']='Gain freeze plus ADC headroom; original8 repeats and2.56MS/s; strict frozen-waveform RF gates passed; no model or PL changes';receipt['physical_acceptance_pending']=True;receipt['physical_cold_boot_verified_for_this_software']=False;receipt['initial_activation_boot_id']=previous['boot_id'];receipt['runtime_gates']=gates;receipt['files']['evidence/GAIN_QUALIFIED_GATES.json']=sha(RELEASE/'evidence/GAIN_QUALIFIED_GATES.json')
 for f,digest in receipt['files'].items():assert sha(Path(f) if Path(f).is_absolute() else RELEASE/f)==digest,f
 save(RELEASE/'PROMOTED_RELEASE.json',receipt);run([PY,str(RELEASE/'scripts/run_candidate_finalize_v2.py'),'--legacy-root','/root/amr_rescue_20261025','--model-dir','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16','--npu-sha','cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8','--check']);run(['sync']);return dict(release=str(RELEASE),previous=str(old),staged_not_active=True)
def activate():
 previous=json.loads((ROOT/'DEPLOYMENT_PREVIOUS.json').read_text());assert CURRENT.resolve()==Path(previous['release']) and sha(UNIT)==previous['service_sha256'];assert json.loads((RELEASE/'PROMOTED_RELEASE.json').read_text())['all_promotion_gates_passed'];stop_clean()
 try:
  switch(RELEASE);run(['systemctl','start','rml24-integrated']);h=wait_health(RELEASE);assert sha(UNIT)==previous['service_sha256'];return h
 except Exception:
  rollback();raise
def stop_export():
 h=health();assert h['ready'] and h['release']==str(RELEASE);r=Path(h['run']);stop_clean();s=json.loads((r/'supervisor.json').read_text());f=json.loads((r/'capture/final.json').read_text());rows=[json.loads(x) for x in (r/'capture/records.jsonl').read_text().splitlines()];backend=[json.loads(x) for x in (r/'capture/spectrum_backend.jsonl').read_text().splitlines()];npu=(r/'npu.log').read_text(errors='replace');v=dict(supervisor=s,final=f,rows=[dict(frame_id=x['frame_id'],capture_monotonic_ns=x['capture_monotonic_ns'],clock_id=x['clock_id'],boot_id=x['boot_id'],pred=x['candidate']['pred'],finite=x['candidate']['finite'],center_hz=x['center_hz'],scan_steps=x['scan_steps']) for x in rows],backend_counts=dict(collections.Counter(x['backend_used'] for x in backend)),guard_clean='HARDWARE_GUARD_CLEAN_EXIT' in npu,npu_stop=[x for x in npu.splitlines() if 'NPU_STREAM_STOP' in x],run=str(r));assert s['clean_stop'] and s['stop_errors']==[] and s['rx_restore']==[] and f['restore_errors']==[] and f['ui_failed']==0 and v['guard_clean'];save(ROOT/'POST_EVIDENCE.json',v);return dict(stopped_clean=True,run=str(r),valid=f['valid'])
def final_start():
 assert CURRENT.resolve()==RELEASE and not MARKER.exists();run(['systemctl','start','rml24-integrated']);h=wait_health(RELEASE);assert subprocess.check_output(['systemctl','is-enabled','rml24-integrated']).decode().strip()=='enabled';run(['sync']);return dict(software_restart_verified=True,health=h,physical_cold_boot_pending=True)
def rollback():
 previous=json.loads((ROOT/'DEPLOYMENT_PREVIOUS.json').read_text());old=Path(previous['release'])
 if CURRENT.resolve()==old and health().get('ready'):return dict(already_previous_healthy=True,release=str(old))
 stop_clean();switch(old);run(['systemctl','reset-failed','rml24-integrated']);run(['systemctl','start','rml24-integrated']);h=wait_health(old);return dict(rolled_back=True,health=h)
p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','activate','stop_export','final_start','rollback','health','export']);a=p.parse_args()
if a.action=='health':print('DEPLOY_HEALTH '+json.dumps(health()),flush=True)
elif a.action=='export':print('DEPLOY_EVIDENCE_BEGIN'+base64.b64encode(gzip.compress((ROOT/'POST_EVIDENCE.json').read_bytes())).decode()+'DEPLOY_EVIDENCE_END',flush=True)
else:
 try:
  result=globals()[a.action]();save(ROOT/(a.action+'_DONE.json'),result);print('SOFTWARE_ACTION_DONE '+a.action+' '+json.dumps(result),flush=True)
 except Exception as e:save(ROOT/(a.action+'_ERROR.json'),dict(error=str(e)));raise
