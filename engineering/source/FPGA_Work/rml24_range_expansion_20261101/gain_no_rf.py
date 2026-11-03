from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).parent/'pc/console/vendor'));import pluto_link_probe as l
u=l.scan_usb();assert len(u)==1;r=l.Radio(u[0]);out=[]
try:
 r.set(r.tlo,'powerdown',1)
 for gain in [-89.75,-70,-60,-50,-40,-30,-20,-10,0]:
  r.set(r.tx,'hardwaregain',gain);actual=float(r.get(r.tx,'hardwaregain').split()[0]);assert abs(actual-gain)<.01;out.append(dict(requested=gain,actual=actual,tx_lo_powerdown=r.get(r.tlo,'powerdown')))
finally:
 errors=r.close();assert not errors,errors
Path(__file__).with_name('GAIN_NO_RF_READBACK.json').write_text(json.dumps(dict(rows=out,rf_transmitted=False),indent=2));print('GAIN_NO_RF_READBACK_PASS',len(out))
