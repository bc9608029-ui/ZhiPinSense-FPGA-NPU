from pathlib import Path
import json,hashlib,os,shutil,subprocess,argparse,uuid
ROOT=Path('/root/rml24_final_install_20261031');CURRENT=Path('/opt/rml24-integrated/current')
def run(args):return subprocess.run(list(map(str,args)),check=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def restore():
 backup=ROOT/'backup';state=json.loads((backup/'original_state.json').read_text());run(['systemctl','stop','rml24-integrated'])
 for unit in ('rml24-integrated','rml24-boot-acceptance'):subprocess.run(['systemctl','disable',unit],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 mount=Path('/mnt/rml24-final-rollback');mount.mkdir(exist_ok=True)
 if os.path.ismount(str(mount)):raise RuntimeError('unexpected mounted rollback path')
 run(['mount','-o','rw','/dev/mmcblk0p1',mount])
 try:
  for name in ('download.bit','uEnv.txt'):
   assert sha(backup/name)==state['boot_sha'][name];temp=mount/(name+'.rml24-restore')
   with (backup/name).open('rb') as a,temp.open('wb') as b:shutil.copyfileobj(a,b);b.flush();os.fsync(b.fileno())
   assert sha(temp)==state['boot_sha'][name];os.replace(str(temp),str(mount/name))
  run(['sync'])
 finally:run(['umount',mount])
 old=state['old_current']
 if old:
  temp=CURRENT.with_name('current.rollback');os.symlink(old,str(temp));os.replace(str(temp),str(CURRENT))
 elif CURRENT.is_symlink():CURRENT.unlink()
 for unit,info in state['units'].items():
  p=Path('/etc/systemd/system')/(unit+'.service');saved=backup/(unit+'.service')
  if saved.exists():shutil.copyfile(saved,p)
  elif unit=='rml24-integrated' and p.exists():p.unlink()
 run(['systemctl','daemon-reload'])
 for unit,info in state['units'].items():
  if info['enabled']=='enabled':run(['systemctl','enable',unit])
  elif (Path('/etc/systemd/system')/(unit+'.service')).exists():subprocess.run(['systemctl','disable',unit])
 run(['sync']);(ROOT/'ROLLBACK_CONFIG_RESTORED.json').write_text(json.dumps(dict(state='AWAIT_ORIGINAL_PL_LOAD_BEFORE_OLD_NPU_START',files_preserved=True,generation=uuid.uuid4().hex,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())));print('ROLLBACK_CONFIG_RESTORED_AWAIT_ORIGINAL_PL',flush=True)
def finish():
 assert (ROOT/'ROLLBACK_CONFIG_RESTORED.json').exists()
 for args in [['pgrep','-x','npu_stream'],['pgrep','-f','^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared']]:
  if subprocess.run(args,stdout=subprocess.PIPE).returncode!=1:raise RuntimeError('NPU owner present; do not restart old services')
 receipt=json.loads((ROOT/'PC_ORIGINAL_PL_VERIFIED.json').read_text());rollback=json.loads((ROOT/'ROLLBACK_CONFIG_RESTORED.json').read_text());assert receipt['generation']==rollback['generation'] and receipt['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert receipt['passed'] and receipt['bit_sha256']=='22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9'
 state=json.loads((ROOT/'backup/original_state.json').read_text())
 for unit,info in state['units'].items():
  if unit in ('rml24-ui','rml24-receiver') and info['active'] in ('active','activating'):run(['systemctl','start',unit])
 print('ORIGINAL_RUNTIME_RESTORED',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['restore','finish','restore-and-reboot']);a=p.parse_args()
 if a.action=='finish':finish()
 else:
  restore()
  if a.action=='restore-and-reboot':run(['systemctl','reboot'])
