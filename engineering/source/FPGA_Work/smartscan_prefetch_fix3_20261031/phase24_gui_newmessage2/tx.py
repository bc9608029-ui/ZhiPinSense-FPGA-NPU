from pathlib import Path
import sys,json,time
r=Path(__file__).parent;gui=Path('E:/FPGA_Work/rml24_tx_console_integration_20261031/console');sys.path.insert(0,str(gui));sys.path.insert(0,str(gui.parent/'deps'))
from PyQt5 import QtCore,QtWidgets,QtTest
from app import Window
from tx_core import prepare
app=QtWidgets.QApplication([]);w=Window();w.interpreter.setText(sys.executable);w.uri.setText('usb:1.9.5');w.mode.setCurrentIndex(1);w.message_bank.setCurrentIndex(1);w.message.setValue(2);w.frequency.setText('2400.000000');w.gain.setValue(-40);w.hold.setValue(6);w.duration.setValue(200);w.real.setChecked(True);w.show();assert w.preview();plan=prepare(w.config());assert len(plan)==24
(r/'TRUTH_MAPPING_PC_ONLY.json').write_text(json.dumps([dict(index=i,class_index=x['class_index'],source_sha=x['source_sha256']) for i,x in enumerate(plan)],indent=2));QtTest.QTest.mouseClick(w.start,QtCore.Qt.LeftButton);stopped=False;deadline=time.monotonic()+210
try:
 while time.monotonic()<deadline:
  app.processEvents()
  if w.run_dir and (w.run_dir/'events.jsonl').exists():
   rows=[json.loads(x) for x in (w.run_dir/'events.jsonl').read_text(encoding='utf-8').splitlines()]
   if any(x['event']=='muted' and x['index']==23 for x in rows) and not stopped:
    QtTest.QTest.mouseClick(w.stop,QtCore.Qt.LeftButton);stopped=True
  if w.run_dir and (w.run_dir/'result.json').exists() and not w.running():break
  time.sleep(.02)
 assert not w.running() and stopped,'GUI cycle incomplete'
 result=json.loads((w.run_dir/'result.json').read_text(encoding='utf-8'));tx=[x for x in rows if x['event']=='transmitting'];assert len(tx)==24
 for x,y in zip(tx,plan):assert x['source_sha256']==y['source_sha256']
 assert result['error'] is None and result['restore_status']=='READBACK_RESTORE_OK'
 (r/'GUI_CYCLE_RESULT.json').write_text(json.dumps(dict(run_dir=str(w.run_dir),result=result,events=rows,start_stop_verified=stopped),indent=2));w.grab().save(str(r/'gui_real_cycle.png'));print('GUI_REAL_CYCLE_24_COMPLETE',flush=True)
finally:
 if w.running():
  w.request_stop();deadline=time.monotonic()+20
  while w.running() and time.monotonic()<deadline:app.processEvents();time.sleep(.05)
 w.close();app.processEvents()
