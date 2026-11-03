from pathlib import Path
import json,hashlib,datetime
b=Path(__file__).parent.parent;items=[]
for folder,file in [('phase20_gui_rf_cases','GUI_RF_RESULT.json'),('phase21_gui_24_smoke','GUI_24_RF_RESULT.json'),('phase22_gui_multifrequency','GUI_FREQUENCY_RESULT.json'),('phase23_gui_newmessage1','GUI_24_RF_RESULT.json'),('phase24_gui_newmessage2','GUI_24_RF_RESULT.json')]:
 p=b/folder/file
 if not p.exists():items.append(dict(phase=folder,status='PENDING'));continue
 v=json.loads(p.read_text());items.append(dict(phase=folder,result_file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),kind=v['kind'],denominator=v['denominator'],correct=v['correct'],missing=v['missing'],restore_verified=v['gui_start_stop_and_restore_pass'],failures=[x for x in v['results'] if not x['correct']]))
out=dict(updated=datetime.datetime.now().isoformat(),production_promoted=False,temporary_jtag_only=True,results=items)
(Path(__file__).parent/'CURRENT_RF_EVIDENCE_INDEX.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
