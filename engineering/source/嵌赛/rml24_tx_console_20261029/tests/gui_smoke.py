"""Exercise actual Qt -> QProcess -> offline worker -> stop -> result path."""
from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PyQt5 import QtCore,QtWidgets
from app import Window
from tx_core import ROOT

app=QtWidgets.QApplication([]);w=Window();w.interpreter.setText(sys.executable)
w.show();assert not w.real.isChecked()
w.frequency.setText('2400.0000001');assert not w.preview();assert not w.running()
w.frequency.setText('2400.000001');assert w.preview()
w.frequency.setText('2400.000000');w.duration.setValue(10)
w.begin();deadline=time.monotonic()+15;sent=False
while time.monotonic()<deadline:
 app.processEvents()
 if w.status.text().startswith('离线演练 ·') and not sent:
  w.request_stop();sent=True
 if w.run_dir and (w.run_dir/'result.json').is_file() and not w.running():break
 time.sleep(.02)
if not sent:print(w.log.toPlainText(),flush=True)
assert sent,'preview event did not reach the GUI'
assert not w.running(),'worker did not stop'
result=json.loads((w.run_dir/'result.json').read_text(encoding='utf8'))
assert result['real'] is False and result['error'] is None
assert result['restore_status']=='NOT_APPLICABLE'
assert w.start.isEnabled() and not w.stop.isEnabled()
assert 'WRITE_RESTORE' not in w.status.text()
# Keep evidence; the GUI has visibly processed events from a real subprocess.
(ROOT/'evidence').mkdir(exist_ok=True)
(ROOT/'evidence'/'gui_smoke.json').write_text(json.dumps(dict(result='PASS',
 actual_qprocess=True,real_tx=False,stop_requested=sent,worker_result=result,
 run_dir=str(w.run_dir)),indent=2),encoding='utf8')
w.grab().save(str(ROOT/'evidence'/'gui_after_offline_run.png'))
w.close();app.processEvents()
print('GUI_SMOKE PASS invalid_input=blocked qprocess=real offline=YES stop=clean real_tx=NO')
