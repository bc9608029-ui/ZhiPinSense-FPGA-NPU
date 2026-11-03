from pathlib import Path
import subprocess,sys,json
p=Path(__file__).parent
w=subprocess.Popen([sys.executable,str(p/'watch_and_score.py')],stdout=(p/'watch.log').open('w'),stderr=subprocess.STDOUT)
subprocess.run([sys.executable,str(p/'run_paired_validation.py')],stdout=(p/'run.log').open('w'),stderr=subprocess.STDOUT,check=True);assert w.wait(timeout=2200)==0
score=json.loads((p/'SCORE.json').read_text())[0];events=json.loads((p/'gainfreeze_bw5/VARIABLE_TX_EVENTS.json').read_text());rows=json.loads((p/'CLASSIFICATION_ROWS.json').read_text());a=json.loads((p/'gainfreeze_bw5_CLOCK_PRE.json').read_text());b=json.loads((p/'gainfreeze_bw5_CLOCK_POST.json').read_text());off=(a['offset_ns']+b['offset_ns'])//2;end=max(e['end_qpc_ns'] for e in events);neg=[r for r in rows if r['m']+off>end+3000000000];out=[]
for gain in (-60,-65,-67.5,-70):
 group=[s for s,e in zip(score['rows'],events) if e['tx_gain_db']==gain];out.append(dict(gain=gain,denominator=24,candidate_correct=sum(x['correct'] for x in group),original_path_correct=sum(x['correct'] and x['chosen'].get('combined',0)==0 for x in group),missing=sum(x['chosen'] is None for x in group)))
(p/'ADAPTATION_COVERAGE.json').write_text(json.dumps(dict(groups=out,no_tx_captures=len(neg),no_tx_false_accept=sum(x['ok'] for x in neg),not_deployed=True),indent=2));print('WEAK_RF_COMPLETE_NOT_DEPLOYED',flush=True)
