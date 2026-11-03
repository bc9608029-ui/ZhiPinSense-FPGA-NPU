import sys,json,datetime
from pathlib import Path
sys.path.insert(0,r'E:\AMR_Rescue_20261025')
import pluto_link_probe as link
r=Path(r'E:\rml24_gapfix_execution_20261028')
uris=link.scan_usb();assert len(uris)==1,uris
radio=link.Radio(uris[0])
try:
 before=radio.get(radio.tlo,'powerdown')
 n=link.writeattr(radio.tlo,b'powerdown',b'1');assert n>=0,n
 after=radio.get(radio.tlo,'powerdown');assert after=='1',after
 report=dict(uri=uris[0],previous_tx_lo_powerdown=before,tx_lo_powerdown=after,resume_requires_restore_powerdown_before_tx=True)
 (r/'PAUSE_TX_STATE.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:radio.close()
p=r/'FIX2_FORMAL_PROGRESS.json';v=json.loads(p.read_text());v.update(phase='paused_at_user_request',partial_scan=True,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),baseline_services_restored=True,formal_scan_score_not_produced=True);p.write_text(json.dumps(v,indent=2))
(r/'PAUSE_FIX2.md').write_text('PAUSED BY USER. PC runner/TX stopped; board candidate stopped; baseline UI/RX active. Fixed 233/240 missing0 completed. Scan interrupted: no formal 240 result. TX process was terminated without its finally; separate TX LO powerdown=1 readback verified. Before any future run restore previous powerdown from PAUSE_TX_STATE.json, and use fresh run directories. Preserve partial events and board logs. Do not resume or deploy without user instruction.',encoding='utf-8')
print('PAUSE_COMPLETE')
