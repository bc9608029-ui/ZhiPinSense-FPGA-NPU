import pathlib,hashlib,json,zipfile
p=pathlib.Path(__file__).parent
assert (p/'HANDOFF_SCAN_AUTOTEST.md').exists()
required=['HANDOFF_SCAN_AUTOTEST.md','FINAL_SCAN_AUTOTEST_SUMMARY.json','candidate_v2_fourpage_waterfall_tree.tar.gz','board_runtime_evidence.tar.gz','candidate_v2_detail_audit.json','centered_v2_scope_audit.json','historical_npu_replay_audit.json','PHYSICAL_UI_CONFIRMATION.json','mode_control_audit.json','challenge78_audit.json','challenge78_v2_audit.json']
for n in required:assert (p/n).is_file(),n
warn='This is a PC EVIDENCE bundle. It contains private scoring truth/schedules. Do NOT transfer or extract the whole ZIP on the board. Only the separately audited candidate_v2_fourpage_waterfall_tree.tar.gz is a board source/runtime tree, and it still requires documented external frozen model/legacy dependencies. It is NOT installed as boot default.\n'
(p/'PC_EVIDENCE_ONLY_NOT_BOARD_DEPLOY.txt').write_bytes(warn.encode())
files=[f for f in p.rglob('*') if f.is_file() and 'candidate_archive_parts' not in f.relative_to(p).parts and 'board_evidence' not in f.relative_to(p).parts and f.suffix not in ['.zip'] and not f.name.startswith('rml24_scan_autotest_evidence_20261027.zip') and f.name not in ['DELIVERY_SHA256SUMS.txt','DELIVERY_VERIFICATION.json'] and '__pycache__' not in f.relative_to(p).parts]
files=sorted(files,key=lambda f:str(f.relative_to(p)))
manifest=''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.relative_to(p).as_posix()+'\n' for f in files)
(p/'DELIVERY_SHA256SUMS.txt').write_bytes(manifest.encode());files.append(p/'DELIVERY_SHA256SUMS.txt')
zip_path=p/'rml24_scan_autotest_evidence_20261027.zip'
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f in files:z.write(f,f.relative_to(p).as_posix())
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 for line in manifest.splitlines():
  sha,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==sha,name
report={'files':len(files),'internal_sha_failures':0,'zip_crc_failures':0,'sha256':hashlib.sha256(zip_path.read_bytes()).hexdigest(),'bytes':zip_path.stat().st_size,'kind':'PC_EVIDENCE_NOT_BOARD_DEPLOY'}
(p/'DELIVERY_VERIFICATION.json').write_text(json.dumps(report,indent=2));(p/(zip_path.name+'.sha256')).write_bytes((report['sha256']+'  '+zip_path.name+'\n').encode());print(json.dumps(report))