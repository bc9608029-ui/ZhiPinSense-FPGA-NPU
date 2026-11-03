"""Explicit staged release install; never invoked before all runtime gates pass."""
from pathlib import Path
import argparse,json,hashlib,os,shutil,subprocess,time
ROOT=Path('/root/rml24_final_install_20261031')
SOURCE=Path('/root/rml24_fpga_ui_20261031/delivery_deploy_final')
EXTRAS=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/deployment_files')
CURRENT=Path('/opt/rml24-integrated/current')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(args):return subprocess.run(list(map(str,args)),check=True)
def save(p,value):
 p=Path(p);temp=p.with_name(p.name+'.tmp')
 with temp.open('w') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
 os.replace(str(temp),str(p))
def owners_absent():
 for args in [['pgrep','-x','npu_stream'],['pgrep','-f','^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared']]:
  if subprocess.run(args,stdout=subprocess.PIPE).returncode!=1:raise RuntimeError('NPU owner still active')
def mount_boot(readonly):
 p=Path('/mnt/rml24-final-install');p.mkdir(exist_ok=True)
 if os.path.ismount(str(p)):raise RuntimeError('unexpected boot mount')
 run(['mount','-o','ro' if readonly else 'rw','/dev/mmcblk0p1',p]);return p

def stage():
 gates=json.loads((EXTRAS/'RUNTIME_GATES.json').read_text());assert gates['all_passed'] and gates['fixed_correct']>=235 and gates['search_correct']>=235 and gates['sweep_correct']>=23 and gates['missing']==0
 expected={'candidate/rml24_final/runtime/continuous_sweep.py':'6450f9d02626fcfb6e884dc4e21daee6e0d77f9e0d3b8d7dc20169edc433ae57','candidate/bin/board_ui_live_rml24_final':'4bf71ab48febe9960f00668a06f2f09e20bd937b28ba69f9788ba0b52fbf287a','candidate/rml24_final/board_runtime/standalone_receiver.py':'ffdb47bff6834ca0a6ce267773dc731ebe439d8ce61d3595dbcf381f95be1801','scripts/hardware_restart_guard.py':'129dbc4cfa1135d653c79c3544e35709f25b01832fb8450feca367ff0da1a026','scripts/run_candidate_finalize_v2.py':'bc0e5002859adc64759156e8e007bc6c20780290711b7e7ae4923c15309e73b1'}
 for rel,digest in expected.items():assert sha(SOURCE/rel)==digest,rel
 ROOT.mkdir(exist_ok=False);backup=ROOT/'backup';backup.mkdir();boot_plan=json.loads((EXTRAS/'BOOT_INSTALL_PLAN.json').read_text());boot=mount_boot(True)
 try:
  assert sha(boot/'download.bit')==boot_plan['original_bit_sha256'] and sha(boot/'uEnv.txt')==boot_plan['original_uenv_sha256']
  for name in ('download.bit','uEnv.txt','BOOT.bin','Image','fmqlmp-verify.dtb'):shutil.copyfile(boot/name,backup/name)
 finally:run(['umount',boot])
 assert sha(backup/'download.bit')==boot_plan['original_bit_sha256'];shutil.copytree('/opt/rml24-system',backup/'old_runtime')
 units={}
 for unit in ('rml24-ui','rml24-receiver','rml24-integrated'):
  unitfile=Path('/etc/systemd/system')/(unit+'.service')
  if unitfile.exists():shutil.copyfile(unitfile,backup/(unit+'.service'))
  enabled=subprocess.run(['systemctl','is-enabled',unit],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True).stdout.strip();active=subprocess.run(['systemctl','show',unit,'-p','ActiveState','--value'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True).stdout.strip();units[unit]=dict(enabled=enabled,active=active)
 if CURRENT.exists() and not CURRENT.is_symlink():raise RuntimeError('refuse non-symlink current')
 save(backup/'original_state.json',dict(units=units,old_current=os.readlink(str(CURRENT)) if CURRENT.is_symlink() else None,boot_sha={p.name:sha(p) for p in backup.iterdir() if p.is_file()}))
 release=Path('/opt/rml24-integrated/releases')/('r'+str(int(time.time())));release.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(SOURCE,release)
 for name in ('deployment_launcher.py','evidence_retention.py','boot_recovery.py','collect_status.py','BOOT_INSTALL_PLAN.json','rml24-integrated.service'):shutil.copyfile(EXTRAS/name,release/name)
 files=json.loads((release/'evidence/CANDIDATE_SOURCE_IDENTITY.json').read_text());files['evidence/CANDIDATE_SOURCE_IDENTITY.json']=sha(release/'evidence/CANDIDATE_SOURCE_IDENTITY.json')
 for name in ('deployment_launcher.py','evidence_retention.py','boot_recovery.py','collect_status.py','BOOT_INSTALL_PLAN.json'):files[name]=sha(release/name)
 external={'/root/amr_rescue_20261025/build/npu_stream':'cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8','/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared':'7b185cad8aaf526344a36666a90071e59577a2fa1488a7f8f0523ce437bc0af9','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json':'28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw':'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'};files.update(external)
 for name,digest in files.items():assert sha(Path(name) if Path(name).is_absolute() else release/name)==digest,name
 save(release/'PROMOTED_RELEASE.json',dict(all_promotion_gates_passed=True,promotion_scope='Runtime software/RF gates; physical cold-boot acceptance remains pending',physical_acceptance_pending=True,files=files,boot=boot_plan,initial_activation_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),runtime_gates=gates))
 save(ROOT/'STAGED.json',dict(release=str(release),backup=str(backup),state='STAGED_NOT_ACTIVE'));print('RELEASE_STAGED '+str(release),flush=True)

def activate():
 state=json.loads((ROOT/'STAGED.json').read_text());release=Path(state['release']);receipt=json.loads((release/'PROMOTED_RELEASE.json').read_text());assert receipt['all_promotion_gates_passed'];program=json.loads((ROOT/'PC_PL_PROGRAM_VERIFIED.json').read_text());assert program['passed'] and program['bit_sha256']==receipt['boot']['candidate_bit_sha256'] and program['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip();owners_absent();assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
 for unit in ('rml24-ui','rml24-receiver'):assert subprocess.run(['systemctl','is-active','--quiet',unit]).returncode!=0
 probe=subprocess.run(['/root/rml24_fpga_diag_1793380588/scan_xrt','--probe'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=20);assert probe.returncode==0 and 'SMARTSCAN_PROBE version=1 idle=1' in probe.stdout and 'error=0' in probe.stdout
 bit=ROOT/'new.bit';assert sha(bit)==receipt['boot']['candidate_bit_sha256']
 boot=mount_boot(False)
 try:
  assert sha(boot/'download.bit')==receipt['boot']['original_bit_sha256'] and sha(boot/'uEnv.txt')==receipt['boot']['original_uenv_sha256']
  for source,name,digest in [(bit,'download.bit',receipt['boot']['candidate_bit_sha256']),(EXTRAS/'uEnv.integrated.txt','uEnv.txt',receipt['boot']['candidate_uenv_sha256'])]:
   temp=boot/(name+'.rml24-new')
   with source.open('rb') as src,temp.open('wb') as dst:shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
   assert sha(temp)==digest;os.replace(str(temp),str(boot/name))
  run(['sync']);assert sha(boot/'download.bit')==receipt['boot']['candidate_bit_sha256'] and sha(boot/'uEnv.txt')==receipt['boot']['candidate_uenv_sha256']
 finally:run(['umount',boot])
 CURRENT.parent.mkdir(parents=True,exist_ok=True);temp=CURRENT.with_name('current.next')
 if temp.exists() or temp.is_symlink():raise RuntimeError('unexpected pending current link')
 os.symlink(str(release),str(temp));os.replace(str(temp),str(CURRENT));shutil.copyfile(EXTRAS/'rml24-integrated.service','/etc/systemd/system/rml24-integrated.service');run(['systemctl','daemon-reload']);run(['systemctl','disable','rml24-ui','rml24-receiver']);run(['systemctl','enable','rml24-integrated']);run(['systemctl','start','rml24-integrated']);save(ROOT/'ACTIVATED.json',dict(release=str(release),sd_bit_sha=receipt['boot']['candidate_bit_sha256'],sd_uenv_sha=receipt['boot']['candidate_uenv_sha256'],physical_acceptance_pending=True));run(['sync']);print('INTEGRATED_RELEASE_ACTIVATED',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','activate']);a=p.parse_args();globals()[a.action]()
