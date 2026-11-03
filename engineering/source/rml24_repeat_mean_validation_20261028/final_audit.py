import gzip,hashlib,json,sys
from pathlib import Path
r=Path(__file__).parent;d=r.parent/'rml24_mainchain_diagnostic_20261028'
sys.path.insert(0,str(d));from strict_promotion_gate import evaluate
e=json.loads(gzip.decompress((r/'evidence.json.gz').read_bytes()))
manifest=d/'CANDIDATE_FREEZE.json';checks=[]
checks.append(dict(check='frozen_manifest_identity',passed=hashlib.sha256(manifest.read_bytes()).hexdigest()=='69a6775b61a7633bb8c20d0c46ff06e1c01ec3ab76c2757ca2afa82b3db1e6f1'))
for f in json.loads(manifest.read_text())['files']:
    checks.append(dict(check='local_source:'+Path(f['path']).name,passed=hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()==f['sha256']))
boardpaths={'repeat_mean_candidate.py':'/root/rml24_mainchain_diagnostic_20261028/repeat_mean_candidate.py',
 'receiver_repeat_mean_v1.py':'/root/rml24_mainchain_diagnostic_20261028/receiver_repeat_mean_v1.py',
 'run_repeat_mean_v1.sh':'/root/rml24_standalone_execution_20261027/candidate/rml24_final/board_runtime/run_repeat_mean_v1.sh'}
for name,path in boardpaths.items():
    checks.append(dict(check='board_source:'+name,passed=e['source_hashes'][path]==hashlib.sha256((d/name).read_bytes()).hexdigest()))
for name,sha in {'rml24-ui.service':'6ee4461dfae6f1b513e1ae136dc489982ab95318e6aa3b8213654a17e2b8e00e',
                 'rml24-receiver.service':'febdfe0940585b56d6725f04fdcad1a8a71b9fd703a3a4bc5fc6493b34229c7e'}.items():
    checks.append(dict(check='baseline_unit:'+name,passed=e['baseline_unit_hashes'][name]==sha))
scores={}
per_class_changes=[]
for name in ['candidate_fixed02','candidate_scan01']:
    score=json.loads((r/(name+'_score.json')).read_text());scores[name]={k:v for k,v in score.items() if k!='rows'}
    baseline_name='formal_fixed01' if name=='candidate_fixed02' else 'formal_scan01'
    baseline=json.loads((r.parent/'rml24_standalone_execution_20261027'/(baseline_name+'_score.json')).read_text())
    for label in range(24):
        before=sum(v['label']==label and v['pred']==label for v in baseline['rows'])
        after=sum(v['label']==label and v['pred']==label for v in score['rows'])
        if before!=after:per_class_changes.append(dict(run=name,label=label,before=before,after=after,regression=after<before))
    rec=e[name]
    checks.append(dict(check=name+':fixed_denominator',passed=score['denominator']==240 and len(score['rows'])==240))
    checks.append(dict(check=name+':rx_restore',passed=rec['final']['restore_errors']==[]))
    checks.append(dict(check=name+':ui_delivery',passed=rec['final']['ui_failed']==0))
    different=[v['frame_id'] for v in rec['records'] if v['finite'] and len(set(v.get('window_predictions') or []))!=1]
    checks.append(dict(check=name+':identical_repeated_input_predictions',passed=not different,frame_ids=different))
cleanup=e.get('cleanup',{})
checks.append(dict(check='baseline_restoration',passed=cleanup.get('baseline_start_returncode')==0))
gate=evaluate(r.parent/'rml24_standalone_execution_20261027/formal_fixed01_score.json',
              r.parent/'rml24_standalone_execution_20261027/formal_scan01_score.json',
              r/'candidate_fixed02_score.json',r/'candidate_scan01_score.json')
report=dict(status='COMPLETE_REQUIRES_REVIEW',scores=scores,gate=gate,checks=checks,
            passed=sum(v['passed'] for v in checks),total=len(checks),production_promoted=False,
            per_class_changes=per_class_changes,per_class_review_required=any(v['regression'] for v in per_class_changes),
            note='Same existing 240 sources, fresh RF captures; not unseen-waveform generalization')
(r/'FINAL_VALIDATION_SUMMARY.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))
for c in checks:
    if not c['passed']:print('AUDIT_NOT_PASS',c)
