from pathlib import Path
import tempfile,json,gzip,base64,subprocess,sys,runpy,shutil
from types import SimpleNamespace
source=Path(__file__).parent/'audit_formal.py';real=subprocess.run

def case(mode,rows,expected_correct,expected_missing):
 with tempfile.TemporaryDirectory() as tmp:
  r=Path(tmp);d=r/'test';d.mkdir();tx=r/'test_tx';tx.mkdir();shutil.copyfile(source,r/'audit_formal.py');(r/'FORMAL_PLAN.json').write_text(json.dumps(dict(runs=[dict(name='test',mode=mode,n=2,hz=2400000000,minimum_correct=2)])))
  (d/'DEVICE_STATUS.json').write_text(json.dumps(dict(stage='DEVICE_PHASE_ENDED_ORIGINAL_RESTORED',board_evidence='/root/fake')));(d/'clock_pre.json').write_text(json.dumps(dict(offset_ns=0,uncertainty_ms=1)))
  truth=[dict(seq=i,file=str(i),source_sha256='x',label=i+3) for i in range(2)];events=[dict(x,index=i,start_ns=i*10000000000,end_ns=i*10000000000+5000000000) for i,x in enumerate(truth)]
  (tx/'plan_private.json').write_text(json.dumps(truth));(tx/'events_private.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in events));(tx/'restore.json').write_text(json.dumps(dict(errors=[],readback=[dict(ok=True)])))
  n=sum(x['finite'] for x in rows);v=dict(summary=dict(rc=0,supervisor=dict(clean_stop=True),guard_clean=True,guard_marker_absent=True,final=dict(ui_failed=0,restore_errors=[],valid=n),backend_counts=dict(fpga=n)),npu_stop=['NPU_STREAM_STOP frames=%d apply=1 reset=%d discipline=1'%(n*8,max(0,n*8-1))],rows=rows)
  payload=base64.b64encode(gzip.compress(json.dumps(v).encode())).decode();subprocess.run=lambda *a,**kw:SimpleNamespace(stdout=('FORMAL_EVIDENCE_BEGIN\n'+payload+'\nFORMAL_EVIDENCE_END').encode());old=sys.argv;sys.argv=['audit','test']
  try:runpy.run_path(str(r/'audit_formal.py'),run_name='__main__')
  finally:sys.argv=old;subprocess.run=real
  result=json.loads((d/'SCORE.json').read_text());assert result['correct']==expected_correct and result['missing']==expected_missing;assert result['promotion_gate_pass']==(expected_correct==2 and expected_missing==0)
def row(i,t,p,finite=True,lo=2400000000):return dict(frame_id=i,capture_time_ns=t,pred=p,finite=finite,repeat_average=8 if finite else None,scan_steps=[dict(lo_hz=lo)],center_hz=2400000000)
case('FIXED',[row(0,1600000000,2),row(1,2000000000,3)],0,1)
case('FIXED',[row(0,1600000000,3),row(1,11600000000,4)],2,0)
case('CONTINUOUS_SCAN',[row(0,1600000000,3,lo=2395000000),row(1,1700000000,-1,False),row(2,2000000000,3),row(3,11600000000,4)],1,0)
print('FORMAL_SCORING_SELFTEST 3/3 PASS; no hardware accessed')
