from pathlib import Path
import hashlib,json,zipfile
P=Path(__file__).parent;Z=P.parent/(P.name+'.zip')
files=sorted([p for p in P.rglob('*') if p.is_file() and not any(x in p.relative_to(P).parts for x in ['__pycache__','xsim.dir','.Xil']) and p.name not in ['SHA256SUMS.txt','DELIVERY_VERIFICATION.json'] and p.suffix not in ['.wdb','.pb','.zip']],key=lambda f:f.relative_to(P).as_posix())
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(P).as_posix()+'\n' for p in files)
(P/'SHA256SUMS.txt').write_bytes(manifest.encode('utf-8'));files.append(P/'SHA256SUMS.txt')
with zipfile.ZipFile(Z,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files:z.write(p,P.name+'/'+p.relative_to(P).as_posix())
with zipfile.ZipFile(Z) as z:
 assert z.testzip() is None
 for line in manifest.splitlines():
  sha,name=line.split('  ',1);assert hashlib.sha256(z.read(P.name+'/'+name)).hexdigest()==sha,name
 for required in ['HANDOFF_FPGA_EXECUTION.md','RESULTS_SUMMARY.json','REMAINING_WORK.md','baseline_backup/runtime_before.tar.gz','baseline_backup/sd_boot_before.tar.gz']:
  assert P.name+'/'+required in z.namelist(),required
r={'zip':str(Z),'sha256':hashlib.sha256(Z.read_bytes()).hexdigest(),'bytes':Z.stat().st_size,'files':len(files),'internal_sha_failures':0,'zip_crc_failures':0,'status':'RTL_SIM_AND_FMQL_STANDALONE_IMPLEMENTATION_VERIFIED_PS_PL_AB_PENDING','kind':'TEST_EVIDENCE_AND_RECOVERY_BACKUPS_NOT_BOARD_DEPLOY'}
(P/'DELIVERY_VERIFICATION.json').write_text(json.dumps(r,indent=2),encoding='utf-8');Z.with_suffix(Z.suffix+'.sha256').write_bytes((r['sha256']+'  '+Z.name+'\n').encode('utf-8'));print(json.dumps(r))