from pathlib import Path
import json,time,ctypes,hashlib,zipfile
p=Path(__file__).parent;pid=int((p/'MASTER_PID.txt').read_text(encoding='utf-8-sig'));k=ctypes.windll.kernel32;k.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint];k.OpenProcess.restype=ctypes.c_void_p;k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.CloseHandle.argtypes=[ctypes.c_void_p];h=k.OpenProcess(0x100000,False,pid);last='';deadline=time.monotonic()+14400
try:
 while time.monotonic()<deadline:
  alive=bool(h and k.WaitForSingleObject(h,0)==258)
  try:status=json.loads((p/'STATUS.json').read_text())
  except (FileNotFoundError,json.JSONDecodeError):status=dict(stage='STARTING')
  try:results=json.loads((p/'RESULTS.json').read_text())
  except (FileNotFoundError,json.JSONDecodeError):results=[]
  state=dict(controller_alive=alive,status=status,completed_rounds=len(results),results=results);sig=json.dumps([status,len(results),alive])
  if sig!=last:(p/'MONITOR.json').write_text(json.dumps(state,indent=2));last=sig
  if not alive:
   deployed=json.loads((p/'DEPLOYMENT_RESULT.json').read_text()) if (p/'DEPLOYMENT_RESULT.json').exists() else None;lines=['# Gain adaptation execution handoff','',status.get('stage','UNKNOWN'),'Software deployed: '+str(bool(deployed and deployed.get('deployed'))),'']
   for r in results:lines.append('- %s: %s/%s, missing%s, required%s, pass%s.'%(r['name'],r['correct'],r['denominator'],r['missing'],r['minimum_correct'],r['gate_pass']))
   lines+=['','Source identities and user authorization are retained. Model,8-repeat frame,2.56MS/s and FPGA bit unchanged.','No promotion if any gate failed. Read per-round SCORE.json and EVIDENCE.json.gz.','If deployed, inspect actual production post24 score, software restart receipt and rollback path. Physical cold-power-cycle remains unobserved.','These are fresh RF acquisitions of existing frozen waveforms, not unseen-signal generalization.'];(p/'HANDOFF_FINAL.md').write_text(chr(10).join(lines)+chr(10));(p/'MONITOR_FINAL.json').write_text(json.dumps(state,indent=2));archive=p/'gain_centerfix_execution_evidence.zip';files=[f for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f!=archive and f.suffix.lower() in ('.json','.jsonl','.md','.py','.txt','.log','.gz') and f.stat().st_size<8*1024*1024];blobs={f.relative_to(p).as_posix():f.read_bytes() for f in files};identity={n:hashlib.sha256(b).hexdigest() for n,b in blobs.items()}
   with zipfile.ZipFile(str(archive),'w',compression=zipfile.ZIP_DEFLATED) as z:
    for n,b in blobs.items():z.writestr(n,b)
    z.writestr('SHA256SUMS.json',json.dumps(identity,indent=2))
   with zipfile.ZipFile(str(archive)) as z:
    assert z.testzip() is None
    for n,d in identity.items():assert hashlib.sha256(z.read(n)).hexdigest()==d
   (p/(archive.name+'.sha256')).write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+chr(10));break
  time.sleep(10)
finally:
 if h:k.CloseHandle(h)
