"""Recover verified test data to F, release only its raw copies, finish tests."""
import datetime,hashlib,importlib.util,json,os,shlex,subprocess,sys,tarfile,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('helpers',HERE/'run_tests.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def status(stage,**v):
 h.write(HERE/'RESUME_STATUS.json',dict(stage=stage,time=datetime.datetime.now().astimezone().isoformat(),pid=os.getpid(),**v));print(stage,flush=True)
def recover_space():
 base=json.loads((HERE/'remote_root.json').read_text())['root']
 code=r'''
from pathlib import Path
import sys,json,hashlib
base=Path(sys.argv[1]);assert base.parent==Path('/root') and base.name.startswith('rml24_param_exec_')
files={}
for p in sorted(base.rglob('*')):
 if p.is_symlink():raise RuntimeError('unexpected symlink in test tree')
 if p.is_file():
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1048576),b''):h.update(b)
  files[p.relative_to(base).as_posix()]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
print(json.dumps({'base':str(base),'files':files}))
'''
 archive=HERE/'raw_before_space_recovery.tar';manifest_path=HERE/'raw_before_space_recovery_manifest.json'
 receipt=HERE/'SPACE_RECOVERY_RECEIPT.json'
 if receipt.exists():return
 if not archive.exists():
  status('HASHING_REMOTE_TEST_EVIDENCE')
  manifest=json.loads(h.pyremote(code,[base],timeout=600).stdout);h.write(manifest_path,manifest)
  status('STREAMING_RAW_BACKUP_TO_F',files=len(manifest['files']))
  temp=archive.with_suffix('.tar.partial')
  with temp.open('wb') as f,(HERE/'raw_backup_ssh.log').open('w',encoding='utf8') as log:
   r=subprocess.run([*h.SSH,'tar -C '+shlex.quote(base)+' -cf - .'],stdout=f,stderr=log,timeout=1800,env=h.ENV)
  if r.returncode:raise RuntimeError('backup stream failed; original data retained')
  os.replace(temp,archive)
 else:manifest=json.loads(manifest_path.read_text(encoding='utf8'))
 status('VERIFYING_EVERY_ARCHIVED_FILE',archive_bytes=archive.stat().st_size)
 expected=manifest['files'];seen=set()
 with tarfile.open(archive,'r:') as tar:
  for member in tar:
   if member.isdir():continue
   name=member.name.removeprefix('./')
   if not member.isfile() or name not in expected:raise RuntimeError('unexpected archive member '+name)
   if member.size!=expected[name]['bytes']:raise RuntimeError('archive size mismatch '+name)
   digest=hashlib.sha256();stream=tar.extractfile(member)
   for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
   if digest.hexdigest()!=expected[name]['sha256']:raise RuntimeError('archive SHA mismatch '+name)
   seen.add(name)
 if seen!=set(expected):raise RuntimeError('archive member set mismatch')
 # Send only raw-file hashes for files already independently verified on F.
 raw={n:v for n,v in expected.items() if n.endswith('.raw.npy')}
 status('RELEASING_ONLY_VERIFIED_TEST_RAW_COPIES',raw_files=len(raw))
 cleanup=r'''
from pathlib import Path
import sys,json,hashlib,shutil
base=Path(sys.argv[1]);assert base.parent==Path('/root') and base.name.startswith('rml24_param_exec_')
rows=json.loads(sys.argv[2]);deleted=[];total=0
for name,v in rows.items():
 p=base/name
 assert name.endswith('.raw.npy') and not p.is_symlink() and base.resolve() in p.resolve().parents
 if not p.exists():continue
 assert p.stat().st_size==v['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==v['sha256'],'raw changed before cleanup'
 p.unlink();deleted.append(name);total+=v['bytes']
result={'deleted_files':deleted,'deleted_bytes':total,'free_bytes':shutil.disk_usage(base).free,'original_logs_and_tensors_retained':True}
(base/'space_recovery_receipt.json').write_text(json.dumps(result))
print(json.dumps(result))
'''
 # stdin carries the Python source; a bounded ~few-thousand-record JSON argument remains below ARG_MAX.
 remote_manifest=base+'/verified_raw_cleanup_manifest.json'
 local_manifest=HERE/'verified_raw_cleanup_manifest.json';h.write(local_manifest,raw);h.push(local_manifest,remote_manifest)
 cleanup=cleanup.replace('rows=json.loads(sys.argv[2])','rows=json.loads(Path(sys.argv[2]).read_text())')
 result=json.loads(h.pyremote(cleanup,[base,remote_manifest],timeout=600).stdout)
 result.update(local_archive=str(archive),all_archive_member_sha_verified=True)
 h.write(receipt,result)

def main():
 recover_space()
 info=json.loads((HERE/'board_preflight.json').read_text());base=json.loads((HERE/'remote_root.json').read_text())['root']
 # Preserve the previous no-space attempt, including the completed TX plan and restore receipt.
 if not (HERE/'full45/score.json').exists():
  folder=HERE/'full45'
  if folder.exists():folder.rename(HERE/('full45_failed_no_space_'+str(int(time.time()))))
  stopped=False
  try:
   h.remote('systemctl stop rml24-receiver.service');stopped=True
   h.experiment(info,base,'full45',45,10)
  finally:
   process_file=HERE/'full45/rx_process.json'
   if process_file.exists():
    record=json.loads(process_file.read_text());pid=record['pid'];out=record['out']
    code="import pathlib,os,signal,time; p=pathlib.Path('/proc')/"+repr(str(pid))+"/'cmdline'; s=p.read_bytes().decode(errors='replace') if p.exists() else '';\nif 'parameter_rx.py' in s and "+repr(out)+" in s:\n os.kill("+str(pid)+",signal.SIGINT)\n for i in range(100):\n  if not p.exists():break\n  time.sleep(.1)\n else:raise RuntimeError('owned RX did not finish; no service restart')\n"
    h.pyremote(code)
   if stopped and info['receiver_was_active']:h.remote('systemctl start rml24-receiver.service')
 scores={}
 for label in ['smoke35','smoke25','smokeAGC','smoke45','full35','full25','fullAGC','full45']:
  scores[label]=json.loads((HERE/label/'score.json').read_text())
 h.write(HERE/'PARAMETER_RESULTS.json',dict(scores=scores,production_changed=False,
         independent_message_generalization_proven=False,second_session_revalidation_pending=True,
         data_backup_verified=True,failed_attempt_retained=True))
 h.status('PARAMETER_TESTS_COMPLETE',scores={k:v['correct'] for k,v in scores.items()})
 status('PARAMETER_COMPLETE_STARTING_FPGA')
 with (HERE/'fpga_supervised.log').open('w',encoding='utf8') as log:
  result=subprocess.run([sys.executable,'-I',str(HERE/'run_fpga_tests.py')],stdout=log,stderr=subprocess.STDOUT,env=h.ENV)
 status('EXECUTION_FINISHED',fpga_rc=result.returncode,production_promoted=False)
 return result.returncode
if __name__=='__main__':
 if '--fpga-only' in sys.argv:
  status('FPGA_ONLY_RESUME_PARAMETERS_ALREADY_COMPLETE')
  old=HERE/'fpga_execution'
  if old.exists():
   target=HERE/('fpga_execution_attempt_compile_'+str(int(time.time())))
   assert old.resolve().parent==HERE.resolve() and target.resolve().parent==HERE.resolve()
   old.rename(target)
  result=subprocess.run([sys.executable,'-I',str(HERE/'run_fpga_tests.py')],env=h.ENV)
  status('FPGA_ONLY_ENDED',rc=result.returncode);raise SystemExit(result.returncode)
 try:raise SystemExit(main())
 except Exception as e:
  status('FAILED_WITH_EVIDENCE_RETAINED',error=str(e));(HERE/'resume_failure.log').write_text(traceback.format_exc());raise
