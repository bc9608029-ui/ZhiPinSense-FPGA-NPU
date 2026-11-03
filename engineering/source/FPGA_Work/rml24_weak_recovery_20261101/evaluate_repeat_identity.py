from pathlib import Path
import sys,json,numpy as np
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');sys.path.insert(0,str(base));from repeat_consistency import repeat_consistency;from adaptive_repeat_recovery import train
root=Path('/root/rml24_weak_adaptive_rf_20261101');rows=json.loads((root/'CLASSIFICATION_RESULT.json').read_text())['rows'];out=[]
for x in rows:
 if not x['recovered'] or not x['metadata'].get('temporal_combine',0):continue
 y=np.load(Path(x['folder'])/x['file']);d=repeat_consistency(y,train,repeats=8);out.append(dict(m=x['capture_mono_ns'],gate=d,pred=x['prediction']['pred']));(root/'REPEAT_IDENTITY_GATE_PROGRESS.json').write_text(json.dumps(out,indent=2))
(root/'REPEAT_IDENTITY_GATE.json').write_text(json.dumps(dict(rows=out,threshold_frozen_before_real_evaluation=.8,production_changed=False),indent=2));print('REPEAT_IDENTITY_GATE_COMPLETE',len(out),flush=True)
