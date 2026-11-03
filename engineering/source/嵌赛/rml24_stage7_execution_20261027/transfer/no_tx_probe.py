import sys,json,time
from pathlib import Path
import numpy as np
r=Path('/root/rml24_stage7_execution_20261027');sys.path.insert(0,'/root/amr_rescue_20261025');sys.path.insert(0,str(r/'final_waterfall_fix1/rml24_final/recovery'));sys.path.insert(0,str(r/'final_waterfall_fix1/rml24_final/runtime'));from pluto_link_probe import Radio,scan_usb;import candidate_two_dc;from receiver_core import recover_frame;from ui_event import build_ui_event,build_board_ui_result
out=r/'no_tx_probe';out.mkdir(exist_ok=False);uris=scan_usb();assert len(uris)==1;radio=Radio(uris[0]);rows=[]
try:
 radio.config_rx()
 for seq in range(3):
  y=radio.receive(65536);np.save(out/('%04d.raw.npy'%seq),y);arm=dict(pred=-1);rejected=False
  try:recover_frame(y,candidate_two_dc.recover)
  except Exception as exc:arm.update(error=type(exc).__name__+': '+str(exc));rejected=True
  event=build_ui_event(seq,arm);rows.append(dict(seq=seq,recovery_rejected=rejected,error=arm.get('error'),canonical_state=event['state'],prediction=event['prediction'],no_classification_sent=build_board_ui_result(event) is None));time.sleep(.1)
finally:restore=radio.close()
doc=dict(kind='REAL_RX_WITH_PC_TX_CLOSED',npu_called=False,records=rows,restore_errors=restore,all_rejected_without_class=all(x['recovery_rejected'] and x['prediction'] is None and x['no_classification_sent'] for x in rows));(out/'result.json').write_text(json.dumps(doc,indent=2));print(json.dumps(doc));assert doc['all_rejected_without_class'] and not restore