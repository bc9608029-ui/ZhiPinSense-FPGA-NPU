from pathlib import Path
import json,time,gzip,hashlib,ctypes
p=Path(__file__).resolve().parent.parent;o=p/'monitoring';old=Path('E:/FPGA_Work/rml24_gainfreeze_formal_prep_20261101');pid=int((o/'FORMAL_CONTROLLER_PID.txt').read_text(encoding='utf-8-sig'));k=ctypes.windll.kernel32;k.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint];k.OpenProcess.restype=ctypes.c_void_p;k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.CloseHandle.argtypes=[ctypes.c_void_p];h=k.OpenProcess(0x100000,False,pid);assert h
last='';deadline=time.monotonic()+10800
try:
 while time.monotonic()<deadline:
  alive=k.WaitForSingleObject(h,0)==258;audits=[]
  for name in ('fixed240','search240','sweep24','wide13'):
   f=p/name/'SCORE.json'
   if not f.exists():continue
   s=json.loads(f.read_text());a=json.loads((old/name/'SCORE.json').read_text());newtruth=json.loads((p/(name+'_tx')/'plan_private.json').read_text());oldtruth=json.loads((old/(name+'_tx')/'plan_private.json').read_text());assert [(r['file'],r['source_sha256'],r['label']) for r in newtruth]==[(r['file'],r['source_sha256'],r['label']) for r in oldtruth]
   gained=[];lost=[];fails=[];v=json.loads(gzip.decompress((p/name/'EVIDENCE.json.gz').read_bytes()))
   for r,b,t in zip(s['rows'],a['rows'],newtruth):
    assert r['index']==b['index'] and r['expected']==b['expected']==t['label']
    item=dict(file=t['file'],source_sha256=t['source_sha256'],expected=r['expected'],old_pred=b['pred'],new_pred=r['pred'])
    if r['correct'] and not b['correct']:gained.append(item)
    if b['correct'] and not r['correct']:lost.append(item)
    if not r['correct']:
     fid=r['chosen_frame'];fails.append(dict(item,chosen_frame=fid,missing=r['missing'],nearby=[x for x in v['rows'] if fid is not None and abs(x['frame_id']-fid)<=2]))
   audits.append(dict(round=name,correct=s['correct'],denominator=s['denominator'],required=s['minimum_correct'],missing=s['missing'],gate=s['promotion_gate_pass'],old_gainfreeze_correct=a['correct'],improved_items=gained,regressed_items=lost,failures=fails,score_sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
  all_done=len(audits)==4;passed=all_done and all(r['gate'] for r in audits);r=dict(controller_alive=alive,completed_rounds=len(audits),all_performance_gates=passed,deployed=False,scope='Same frozen waveforms, fresh RF; comparison to previous gainfreeze candidate; not unseen generalization',rounds=audits)
  sig=json.dumps([(x['round'],x['score_sha256']) for x in audits])+str(alive)
  if sig!=last:
   (o/'PAIRED_PROGRESS_AUDIT.json').write_text(json.dumps(r,indent=2));print('AUDIT_UPDATED',len(audits),'controller_alive',alive,flush=True);last=sig
  if all_done or not alive:
   decision='READY_FOR_REVIEW_NOT_DEPLOYED' if passed else 'DO_NOT_PROMOTE'
   lines=['# Performance-preserving receiver candidate audit','',decision,'','No automatic deployment. Original model, bitstream, waveform set and TX precision preserved.']
   for a in audits:lines.append('- %s: %s/%s; required%s; missing%s; prior gainfreeze%s; improved%d; regressed%d.'%(a['round'],a['correct'],a['denominator'],a['required'],a['missing'],a['old_gainfreeze_correct'],len(a['improved_items']),len(a['regressed_items'])))
   lines+=['','Private waveform/source SHA equality checked before comparing scores. Improvements/regressions are paired by waveform; this is not proof of a globally optimal method or unseen-waveform performance.','Single-repeat and high-precision TX research remain separate. Single-repeat actual RF still has errors and is not promoted.']
   (o/'PERFORMANCE_AUDIT_FINAL.md').write_text('\n'.join(lines)+'\n');(o/'PERFORMANCE_AUDIT_FINAL.json').write_text(json.dumps(r,indent=2));break
  time.sleep(20)
finally:k.CloseHandle(h)
