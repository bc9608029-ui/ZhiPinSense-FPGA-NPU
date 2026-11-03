from pathlib import Path
import subprocess,sys,json
p=Path(__file__).parent;w=subprocess.Popen([sys.executable,str(p/'watch_and_score.py')],stdout=(p/'watch.log').open('w'),stderr=subprocess.STDOUT);subprocess.run([sys.executable,str(p/'run_paired_validation.py')],stdout=(p/'run.log').open('w'),stderr=subprocess.STDOUT,check=True);assert w.wait(timeout=2400)==0;results=[]
for score in json.loads((p/'SCORE.json').read_text()):
 mode=score['mode'];ev=json.loads((p/mode/'VARIABLE_TX_EVENTS.json').read_text())
 for gain in (-60,-40):
  group=[s for s,e in zip(score['rows'],ev) if e['tx_gain_db']==gain];results.append(dict(mode=mode,gain=gain,denominator=24,original_correct=sum(x['correct'] and x['chosen'].get('combined',0)==0 for x in group),candidate_correct=sum(x['correct'] for x in group),missing=sum(x['chosen'] is None for x in group)))
(p/'GAINFREEZE_PAIRED_COVERAGE.json').write_text(json.dumps(results,indent=2));print('WEAK_BANDWIDTH_COMPLETE_NOT_DEPLOYED',flush=True)
