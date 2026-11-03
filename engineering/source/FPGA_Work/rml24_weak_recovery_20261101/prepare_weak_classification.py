from pathlib import Path
import json
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031');src=Path('/root/rml24_gain_range_validation_20261101/gainfreeze_bw5');root=Path('/root/rml24_weak_adaptive_classification_20261101');root.mkdir(exist_ok=False);r=json.loads((src/'CAPTURE_RESULT.json').read_text())['rows'];lookup={x['capture_mono_ns']:x for x in r};rows=[]
for item in json.loads((base/'WEAK_SELECTED.json').read_text()):
 d=dict(lookup[item['m']]);d['file']=str(src/d['file']);rows.append(d)
(root/'CAPTURE_RESULT.json').write_text(json.dumps(dict(rows=rows),indent=2));print('WEAK_CLASSIFICATION_INPUTS_READY',len(rows))
