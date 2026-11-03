"""Native Qt + QProcess offline proof. No Radio import, no device access."""
import json
from pathlib import Path
import sys
import time
from PyQt5 import QtCore, QtWidgets as W

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'pc_console'))
from app import Window
from multi_dialog import MultiDialog

app = W.QApplication([])
parent = Window(); parent.interpreter.setText(sys.executable)
dialog = MultiDialog(parent); dialog.show()
checks = []


def until(predicate, seconds=12):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents(); time.sleep(.02)
        if predicate(): return
    raise AssertionError('GUI worker timeout: ' + dialog.summary.text())


try:
    assert not dialog.real.isChecked() and dialog.proc is None
    checks.append('opening does not create a worker or enable real TX')
    dialog.count.setCurrentIndex(2)
    assert len(dialog.config()['lanes']) == 4
    dialog.count.setCurrentIndex(0)
    assert not dialog.lanes[2]['active'].isEnabled()
    dialog.count.setCurrentIndex(2)
    dialog.duration.setValue(30)
    assert dialog.preview() is not None
    app.processEvents()
    dialog.grab().save(str(ROOT / 'MULTI_UI_PREVIEW.png'))
    dialog.start()
    until(lambda: '离线演练已应用' in dialog.summary.text())
    checks.append('Qt start -> actual QProcess -> offline four-lane waveform plan -> acknowledgement')
    assert not dialog.count.isEnabled()
    dialog.scene(1)
    until(lambda: '命令#1已应用' in dialog.log.toPlainText())
    dialog.scene(3)
    until(lambda: '命令#2已应用' in dialog.log.toPlainText())
    dialog.scene(-2)
    until(lambda: '命令#3已应用' in dialog.log.toPlainText())
    dialog.scene(-1)
    until(lambda: '命令#4已应用' in dialog.log.toPlainText())
    dialog.lanes[3]['active'].setChecked(False)
    until(lambda: '命令#5已应用' in dialog.log.toPlainText())
    checks.append('only A / A+B / remove B / all / individual D checkbox')
    dialog.scene(0)
    until(lambda: '命令#6已应用' in dialog.log.toPlainText())
    dialog.request_stop()
    until(lambda: not dialog.running() and '会话结束' in dialog.summary.text())
    result = json.loads((dialog.run_dir / 'result.json').read_text(encoding='utf8'))
    assert result['real'] is False and result['restore_status'] == 'NOT_APPLICABLE'
    assert result['last_scene'] == 0
    checks.append('all silent / cooperative stop / process finished / controls unlocked')
    dialog.start()
    until(lambda: '离线演练已应用' in dialog.summary.text())
    dialog.reject()
    until(lambda: not dialog.running() and not dialog.isVisible())
    checks.append('close while running waits for worker cleanup')
    (ROOT / 'GUI_SMOKE_RESULT.json').write_text(json.dumps(dict(status='PASS_OFFLINE_ONLY',
        checks=checks, real_transmission=False, screenshot='MULTI_UI_PREVIEW.png'), ensure_ascii=False, indent=2), encoding='utf8')
    print('GUI_SMOKE_PASS', len(checks))
finally:
    if dialog.running():
        dialog.request_stop(); until(lambda: not dialog.running())
    dialog.close(); parent.close(); app.processEvents()
