from pathlib import Path
import json,time,subprocess,base64,re,gzip,hashlib
r=Path('E:/FPGA_Work/smartscan_prefetch_fix3_20261031');deadline=time.monotonic()+1800
while True:
 try:v=json.loads((r/'phase3/DEVICE_STATUS.json').read_text())
 except (FileNotFoundError,json.JSONDecodeError):v={}
 if v.get('stage') in ['DEVICE_PHASE_ENDED_ORIGINAL_RESTORED','NO_NEW_BIT_LOADED']:break
 if time.monotonic()>deadline:raise RuntimeError('Phase3 not finished')
 time.sleep(5)
assert not (r/'phase3/FAILURE.json').exists(),'Phase3 failure preserved; do not claim pass'
assert (r/'phase3/CANDIDATE_NPU_RECEIPT.json').exists()
code="""import json,gzip,base64,hashlib
from pathlib import Path
out={}
for name in ['/root/rml24_fix3_1793424504','/root/rml24_fix3_1793424787']:
 p=Path(name);files={}
 for x in p.rglob('*'):
  if x.is_file():
   b=x.read_bytes();files[str(x.relative_to(p))]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
   if x.suffix in ['.json','.log']:files[str(x.relative_to(p))]['text']=b.decode(errors='replace')
 out[name]=files
print('EVIDENCE_BEGIN');print(base64.b64encode(gzip.compress(json.dumps(out).encode())).decode());print('EVIDENCE_END')
"""
b=base64.b64encode(code.encode()).decode();cmd='python3 -c "import base64;exec(base64.b64decode(\''+b+'\'))"'
q=subprocess.run(['powershell','-NoProfile','-File','E:/scan_exec_20261027/serial.ps1','-Command',cmd,'-Seconds','12'],capture_output=True,timeout=40);q.check_returncode();s=q.stdout.decode(errors='replace');(r/'final_collection.log').write_text(s)
m=re.search(r'EVIDENCE_BEGIN\r?\n([A-Za-z0-9+/=\s]+)EVIDENCE_END',s);assert m,'collection incomplete'
data=base64.b64decode(re.sub(r'\s','',m[1]));e=json.loads(gzip.decompress(data));(r/'board_evidence.json.gz').write_bytes(data)
for name,n in [('/root/rml24_fix3_1793424504',8),('/root/rml24_fix3_1793424787',16)]:
 files=e[name]
 for i in range(1,n+1):
  a=json.loads(files['repeat_'+str(i)+'/summary.json']['text']);assert a['passed']==a['executed']==a['expected']==8
  assert all(x['result']['ok'] and x['result']['backend_used']=='fpga' for x in a['results'])
a=json.loads(e['/root/rml24_fix3_1793424787']['auto/summary.json']['text']);assert a['passed']==8 and all(x['result']['backend_used']=='fpga' for x in a['results'])
b=json.loads(e['/root/rml24_fix3_1793424787']['fallback/result.json']['text']);assert b['ok'] and b['backend_used']=='software' and 'driver_launch_failed' in b['fallback_reason']
receipt={'status':'ISOLATED_PREFETCH_DIAGNOSTICS_PASS_NOT_RF_ACCEPTANCE','fixed_matrix_passed':192,'fixed_matrix_total':192,'auto_fpga_passed':8,'intentional_launch_failure_software_fallback':True,'candidate_zero_input_npu_finite':8,'original_bit_restored':v['stage']=='DEVICE_PHASE_ENDED_ORIGINAL_RESTORED','root_cause_proven':False,'rf_tested':False,'production_promoted':False,'bit':json.loads((r/'NEW_BIT_IDENTITY.json').read_text()),'board_evidence_sha256':hashlib.sha256(data).hexdigest()}
(r/'FINAL_DIAGNOSTIC_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print('FINAL_DIAGNOSTIC_AUDIT_PASS',flush=True)
