from pathlib import Path
import sys,json,time
r=Path(__file__).parent;gui=Path('E:/FPGA_Work/rml24_tx_console_timing_update_20261031/console');sys.path.insert(0,str(gui));sys.path.insert(0,'E:/FPGA_Work/rml24_tx_console_integration_20261031/deps')
from PyQt5 import QtCore,QtWidgets,QtTest
from app import Window
from tx_core import prepare
app=QtWidgets.QApplication([]);w=Window();w.interpreter.setText(sys.executable);w.uri.setText('usb:1.9.5');w.modulation.setCurrentIndex(3);w.frequency.setText('2403.600000');w.hold.setValue(30);w.duration.setValue(35);w.real.setChecked(True);w.show();cases=json.loads((r/'PLAN_FROZEN_PC_ONLY.json').read_text())['cases'];rows=[];limit=time.monotonic()+180
try:
 for index,c in enumerate(cases):
  assert time.monotonic()<limit,'GUI RF time budget exceeded'
  w.modulation.setCurrentIndex(c['class_index']);w.message_bank.setCurrentIndex(c['bank']);w.message.setValue(c['message']);w.gain.setValue(c['gain_db']);assert w.preview();wave=prepare(w.config())[0]
  QtTest.QTest.mouseClick(w.start,QtCore.Qt.LeftButton);start=None;stop_at=None;stop_requested=None;deadline=time.monotonic()+35
  while time.monotonic()<deadline:
   app.processEvents()
   if w.run_dir and (w.run_dir/'events.jsonl').exists():
    events=[json.loads(x) for x in (w.run_dir/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    tx=next((x for x in events if x['event']=='transmitting'),None)
    if tx and start is None:start=tx['time_ns'];stop_at=time.monotonic()+10
   if stop_at is not None and time.monotonic()>=stop_at and stop_requested is None:
    stop_requested=time.time_ns();QtTest.QTest.mouseClick(w.stop,QtCore.Qt.LeftButton)
   if w.run_dir and (w.run_dir/'result.json').exists() and not w.running():break
   time.sleep(.02)
  assert not w.running(),'GUI worker still running'
  result=json.loads((w.run_dir/'result.json').read_text(encoding='utf-8'))
  row=dict(index=index,config=c,source_sha=wave['source_sha256'],tx_start_pc_ns=start,stop_request_pc_ns=stop_requested,run_dir=str(w.run_dir),result=result);rows.append(row);(r/'GUI_CASES.json').write_text(json.dumps(rows,indent=2))
  assert start is not None and stop_requested is not None,'actual TX/stop event missing'
  assert result['error'] is None and result['restore_status']=='READBACK_RESTORE_OK' and all(x['ok'] for x in result['restore_readback']),str(result)
  assert w.start.isEnabled() and not w.stop.isEnabled()
 w.grab().save(str(r/'gui_after_real_cases.png'));print('GUI_REAL_START_STOP_1_PASS',flush=True)
finally:
 if w.running():
  w.request_stop();deadline=time.monotonic()+20
  while w.running() and time.monotonic()<deadline:app.processEvents();time.sleep(.05)
 w.close();app.processEvents()
