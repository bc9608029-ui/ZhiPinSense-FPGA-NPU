"""Recover only after a proven new Linux boot that reloaded the frozen PL image."""
from pathlib import Path
import hashlib,json,os,subprocess,uuid
BLOCKED=78

def authorize_recovery(marker,current_boot,cmdline,bit_sha,uenv_sha,expected):
 if not marker.get('boot_id') or marker['boot_id']==current_boot:raise RuntimeError('same/unknown boot fault: never auto-clear')
 if 'rml24_pl_sha256='+expected['candidate_bit_sha256'] not in cmdline.split():raise RuntimeError('missing successful boot PL proof')
 if bit_sha!=expected['candidate_bit_sha256'] or uenv_sha!=expected['candidate_uenv_sha256']:raise RuntimeError('SD boot identity mismatch')
 return True

def inspect_boot_sd(expected):
 mount=Path('/mnt/rml24-integrated-boot-proof');mount.mkdir(exist_ok=True)
 if os.path.ismount(str(mount)):raise RuntimeError('unexpected preexisting boot mount')
 subprocess.run(['mount','-o','ro','/dev/mmcblk0p1',str(mount)],check=True)
 try:
  bit=hashlib.sha256((mount/'download.bit').read_bytes()).hexdigest();env=hashlib.sha256((mount/'uEnv.txt').read_bytes()).hexdigest()
 finally:subprocess.run(['umount',str(mount)],check=True)
 if bit!=expected['candidate_bit_sha256'] or env!=expected['candidate_uenv_sha256']:raise RuntimeError('SD staged identities drifted')
 return bit,env

def prepare_hardware_start(release):
 import fcntl
 state=Path('/var/lib/rml24-fpga-shared-guard');state.mkdir(parents=True,exist_ok=True);lock=(state/'owner.lock').open('a');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  for cmd in [['pgrep','-x','npu_stream'],['pgrep','-f','^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared']]:
   if subprocess.run(cmd,stdout=subprocess.PIPE).returncode!=1:raise RuntimeError('live NPU owner; no hardware startup')
  marker_path=state/'reset_required.json';current=Path('/proc/sys/kernel/random/boot_id').read_text().strip();cmdline=Path('/proc/cmdline').read_text();expected=release['boot'];has_proof='rml24_pl_sha256='+expected['candidate_bit_sha256'] in cmdline.split()
  # First live activation is allowed only in its recorded boot after explicit JTAG
  # programming and without a retained hardware fault. All later boots need proof.
  if not has_proof:
   if marker_path.exists() or current!=release.get('initial_activation_boot_id'):raise RuntimeError('PL boot not proven; no hardware start')
   return dict(initial_jtag_activation=True,recovered=False)
  bit,env=inspect_boot_sd(expected)
  marker=json.loads(marker_path.read_text()) if marker_path.exists() else None
  if marker is not None:authorize_recovery(marker,current,cmdline,bit,env,expected)
  p=subprocess.run(['/root/rml24_fpga_diag_1793380588/scan_xrt','--probe'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=20)
  if p.returncode or 'SMARTSCAN_PROBE version=1 idle=1' not in p.stdout or 'error=0' not in p.stdout:raise RuntimeError('fresh PL idle/version proof failed')
  if marker is None:return dict(boot_proof=True,recovered=False,probe=p.stdout)
  archived=state/('recovered_'+uuid.uuid4().hex+'.json');os.replace(str(marker_path),str(archived));receipt=dict(recovered=True,previous_boot=marker['boot_id'],current_boot=current,archived_fault=str(archived),boot_bit_sha=bit,boot_uenv_sha=env,probe=p.stdout)
  with (state/'last_boot_recovery.json').open('w') as f:json.dump(receipt,f,indent=2);f.flush();os.fsync(f.fileno())
  fd=os.open(str(state),os.O_RDONLY);os.fsync(fd);os.close(fd);return receipt
 finally:lock.close()
