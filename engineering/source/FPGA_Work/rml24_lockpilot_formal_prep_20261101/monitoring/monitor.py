import json,time,hashlib,ctypes
from pathlib import Path
p=Path('E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101');o=Path('E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101/monitoring')
pid=int((o/'FORMAL_CONTROLLER_PID.txt').read_text(encoding='utf-8-sig').strip())
k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p;k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.CloseHandle.argtypes=[ctypes.c_void_p]
h=k.OpenProcess(0x100000,False,pid)
if not h:raise RuntimeError('controller process unavailable')
def collect():
 results=[]
 for name in ('fixed240','search240','sweep24','wide13'):
  f=p/name/'SCORE.json'
  if f.exists():
   b=f.read_bytes();s=json.loads(b);bad=[r for r in s['rows'] if not r['correct']]
   results.append(dict(name=name,correct=s['correct'],denominator=s['denominator'],missing=s['missing'],promotion_gate_pass=s['promotion_gate_pass'],failures=bad,score_sha256=hashlib.sha256(b).hexdigest()))
 return results
start=time.monotonic();previous=''
try:
 while time.monotonic()-start<10800:
  alive=k.WaitForSingleObject(h,0)==258
  try:status=json.loads((p/'STATUS.json').read_text())
  except Exception as e:status=dict(status_read_error=str(e))
  results=collect();done=status.get('stage')=='ALL_ROUNDS_COMPLETE_NOT_DEPLOYED'
  report=dict(controller_alive=alive,formal_status=status,completed_rounds=len(results),results=results,all_four_pass=len(results)==4 and all(r['promotion_gate_pass'] for r in results),deployed=False,action_required=not alive and not done)
  (o/'FORMAL_MONITOR.json').write_text(json.dumps(report,indent=2))
  now=json.dumps([status,len(results),alive])
  if now!=previous:print(now,flush=True);previous=now
  if done or not alive:
   (o/'FORMAL_FINAL_AUDIT.json').write_text(json.dumps(report,indent=2))
   lines=['# Gain-freeze formal RF audit','', 'No automatic deployment performed.','']
   for r in results:lines.append('- %s: %s/%s; missing %s; gate %s'%(r['name'],r['correct'],r['denominator'],r['missing'],r['promotion_gate_pass']))
   lines+=['','All four accuracy gates passed: '+str(report['all_four_pass']), 'Controller ended before completion: '+str(report['action_required']), '', 'These are fresh RF acquisitions of the existing frozen waveforms, not unseen-waveform generalization. Wide13 uses coordinated fixed-frequency RX/TX, not blind whole-band discovery.','If any gate failed, do not promote. Preserve baseline and inspect failures. Synthetic timing research is excluded from formal results.']
   (o/'FORMAL_FINAL_AUDIT.md').write_text('\n'.join(lines));break
  time.sleep(20)
finally:k.CloseHandle(h)
