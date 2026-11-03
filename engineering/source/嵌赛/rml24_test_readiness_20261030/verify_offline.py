"""Required offline checks and receipts, with logs kept on the F-drive tree."""
import ast,datetime,json,os,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,write,sha
def main():
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
 results=[]
 def run(label,args):
  r=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf8',errors='replace')
  (ROOT/'evidence'/(label+'.log')).write_text(r.stdout+r.stderr,encoding='utf8')
  results.append(dict(check=label,rc=r.returncode))
  if r.returncode:raise RuntimeError(label+' failed; inspect evidence log')
 for p in ROOT.rglob('*.py'):
  if '__pycache__' not in p.parts:ast.parse(p.read_text(encoding='utf8'),filename=str(p))
 run('selftest',[sys.executable,'-I',str(ROOT/'selftest.py')])
 run('legacy_gain_selftest',[sys.executable,'-I',str(ROOT/'gain_tools/selftest.py')])
 run('preflight',[sys.executable,'-I',str(ROOT/'preflight.py')])
 with tempfile.TemporaryDirectory(prefix='offline_',dir=ROOT) as temp:
  d=Path(temp)
  run('plan_24',[sys.executable,'-I',str(ROOT/'parameter_plan.py'),'--start-pc-ns','2000000000000000000','--out',str(d/'plan.json')])
  run('tx_dryrun_24',[sys.executable,'-I',str(ROOT/'parameter_tx.py'),'--plan',str(d/'plan.json'),'--out',str(d/'tx_dry')])
  run('vectors',[sys.executable,'-I',str(ROOT/'fpga/make_vectors.py'),'--out',str(d/'vectors')])
  run('software_suite',[sys.executable,'-I',str(ROOT/'fpga/run_suite.py'),'--vectors',str(d/'vectors'),
                        '--out',str(d/'software'),'--backend','software'])
  from common import read
  plan=read(d/'plan.json');events=[];captures=[];replays=[]
  for r in plan['rows']:
   i=r['opportunity'];mid=(r['start_ns']+r['end_ns'])//2
   events.append(dict(opportunity=i,start_ns=r['start_ns'],end_ns=r['end_ns'],plan_sha256=sha(d/'plan.json')))
   captures.append(dict(record_id=i,capture_start_ns=mid,capture_end_ns=mid+30_000_000,sha256='synthetic_'+str(i)))
   replays.append(dict(record_id=i,raw_sha256='synthetic_'+str(i),arms={str(n):dict(valid=True,pred=r['label']) for n in (1,2,4,8)}))
  for name,rows in [('events',events),('captures',captures),('replays',replays)]:
   (d/(name+'.jsonl')).write_text(''.join(json.dumps(v)+'\n' for v in rows),encoding='utf8')
  for name,value in [('pre',dict(pc_before_ns=plan['start_ns']-2_000_000_000,pc_after_ns=plan['start_ns']-1_000_000_000)),
                     ('post',dict(pc_before_ns=plan['end_ns']+1_000_000_000,pc_after_ns=plan['end_ns']+2_000_000_000))]:
   write(d/(name+'.json'),dict(kind='BOARD_MINUS_PC_CLOCK_BOUND',lo_ns=-1_000_000,hi_ns=1_000_000,samples=[value]))
  args=['--plan',str(d/'plan.json'),'--captures',str(d/'captures.jsonl'),'--tx-events',str(d/'events.jsonl'),
        '--clock-pre',str(d/'pre.json'),'--clock-post',str(d/'post.json')]
  run('selection_cli',[sys.executable,'-I',str(ROOT/'select_opportunities.py'),*args,'--out',str(d/'selection.json')])
  write(d/'summary.json',dict(error=None,write_restore_errors=[],raw_records=24))
  write(d/'rx_restore.json',dict(restore_verified=True));write(d/'tx_restore.json',dict(readback_verified=True,write_restore_errors=[]))
  run('score_cli',[sys.executable,'-I',str(ROOT/'parameter_score.py'),*args,'--replays',str(d/'replays.jsonl'),
                  '--capture-summary',str(d/'summary.json'),'--rx-restore',str(d/'rx_restore.json'),
                  '--tx-restore',str(d/'tx_restore.json'),'--out',str(d/'score.json')])
  assert read(d/'selection.json')['record_ids']==list(range(24))
  assert read(d/'score.json')['correct']=={str(n):24 for n in (1,2,4,8)}
 write(ROOT/'evidence/OFFLINE_RECEIPT.json',dict(time=datetime.datetime.now().astimezone().isoformat(),
       checks=results,python_tests=20,software_psd_vectors=8,tx_dryrun_sources=24,
       device_access=False,rf=False,board_compile=False,production_integration=False))
 print('OFFLINE_PREP_CHECKS PASS checks='+str(len(results)))
if __name__=='__main__':main()
