from pathlib import Path
import sys
r=Path(r'E:\rml24_gapfix_execution_20261028')
s=(r/'run_fix2_formal.py').read_text()
s=s.replace("[('fix2_fixed01','FIXED',2400000000,4,1120), ('fix2_scan01','BAND_SCAN',2403600000,6,1610)]","[('fix2_scan02','BAND_SCAN',2403600000,6,1610)]")
assert "('fix2_fixed01'" not in s
s=s.replace('FIX2_FORMAL_PROGRESS.json','FIX2_RESUME_PROGRESS.json')
s=s.replace('collect_fix2_formal.ps1','collect_fix2_resume.ps1').replace('score_fix2_formal.py','score_fix2_resume.py').replace('fix2_formal_ui.log','fix2_resume_ui.log')
(r/'run_fix2_resume.py').write_text(s)
s=(r/'emit_fix2_formal.py').read_text().replace("['fix2_fixed01','fix2_scan01']","['fix2_fixed01','fix2_scan02']")
(r/'emit_fix2_resume.py').write_text(s)
s=(r/'collect_fix2_formal.ps1').read_text().replace('emit_fix2_formal.py','emit_fix2_resume.py').replace('evidence_fix2_formal.json.gz','evidence_fix2_resume.json.gz')
(r/'collect_fix2_resume.ps1').write_text(s)
s=(r/'score_fix2_formal.py').read_text().replace('evidence_fix2_formal.json.gz','evidence_fix2_resume.json.gz')
(r/'score_fix2_resume.py').write_text(s)
sys.path.insert(0,r'E:\AMR_Rescue_20261025')
import pluto_link_probe as link
uris=link.scan_usb();assert len(uris)==1,uris
radio=link.Radio(uris[0])
try:
 assert link.writeattr(radio.tlo,b'powerdown',b'0')>=0
 assert radio.get(radio.tlo,'powerdown')=='0'
 print('TX_LO_RESTORED')
finally:radio.close()
