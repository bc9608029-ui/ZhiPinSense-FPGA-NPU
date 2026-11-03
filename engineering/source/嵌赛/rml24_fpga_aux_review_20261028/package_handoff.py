from pathlib import Path
import shutil,hashlib,json,zipfile
r=Path(r'E:\rml24_fpga_aux_execution_20261028');e=r/'system_evidence';e.mkdir(exist_ok=True)
parent=r.parent/'rml24_gapfix_execution_20261028'
for name in ['fix2_fixed01_score.json','fix2_scan02_score.json','UI_ACCEPTANCE_SUMMARY.json','ui_acceptance_final.log','GMSK_DIAGNOSIS_DECISION.json','allclass_rms_comparison.log','FIX2_REPAIR_NOTES.json','ERROR_COMPARISON.json','post_diagnostic_freeze_check.log']:
 p=parent/name
 if p.exists():shutil.copy2(str(p),str(e/name))
files=[]
for p in r.rglob('*'):
 if not p.is_file() or any(x in ['xsim.dir','__pycache__','.Xil'] for x in p.relative_to(r).parts):continue
 if p.suffix in ['.pb','.jou','.wdb'] or p.name in ['SHA256SUMS.json']:continue
 files.append(p)
manifest={p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
(r/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2))
zpath=r.parent/'rml24_fpga_aux_results_handoff_20261028.zip'
with zipfile.ZipFile(str(zpath),'w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[r/'SHA256SUMS.json']:z.write(str(p),p.relative_to(r).as_posix())
with zipfile.ZipFile(str(zpath)) as z:
 assert z.testzip() is None
 for n,h in manifest.items():assert hashlib.sha256(z.read(n)).hexdigest()==h,n
h=hashlib.sha256(zpath.read_bytes()).hexdigest();Path(str(zpath)+'.sha256').write_text(h+'  '+zpath.name+'\n')
print(json.dumps(dict(zip=str(zpath),sha256=h,bytes=zpath.stat().st_size,verified_content_files=len(manifest),handoff_sha256=manifest['NEXT_AGENT_HANDOFF.md']),indent=2))
