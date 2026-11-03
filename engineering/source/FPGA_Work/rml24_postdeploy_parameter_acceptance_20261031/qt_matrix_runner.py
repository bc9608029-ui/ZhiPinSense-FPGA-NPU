import argparse,sys,os,json,time,hashlib,itertools
from pathlib import Path
BASE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--console',default=r'E:\FPGA_Work\rml24_tx_console_timing_update_20261031\console');p.add_argument('--transmit',action='store_true');p.add_argument('--limit',type=int,default=0);a=p.parse_args()
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path[:0]=[a.console,r'E:\FPGA_Work\rml24_tx_console_integration_20261031\deps']
from PyQt5 import QtWidgets,QtCore,QtTest
import app
src=Path(a.console).resolve();out=BASE/('session_'+str(time.time_ns()));out.mkdir()
(out/'source_sha.json').write_text(json.dumps({str(x.relative_to(src)):hashlib.sha256(x.read_bytes()).hexdigest() for x in src.rglob('*.py')},indent=2))
app.ROOT=out
q=QtWidgets.QApplication([]);w=app.Window();w.show();w.interpreter.setText(sys.executable)
original=w.launch
def launch(args):
 assert '--scan' not in args
 args=[str(src/'tx_worker.py') if x==str(out/'tx_worker.py') else x for x in args]
 original(args)
w.launch=launch
cases=list(itertools.product(range(w.modulation.count()),[(0,1),(0,10),(1,1),(1,2)],['2398','2400','2403.6'],[-40,-50,-60]))
if a.limit:cases=cases[:a.limit]
def pump_until(test,timeout=30):
 end=time.monotonic()+timeout
 while not test():
  q.processEvents();QtTest.QTest.qWait(30)
  if time.monotonic()>end:raise TimeoutError('Qt session timeout')
for i,(cl,(bank,msg),freq,gain) in enumerate(cases):
 w.message_bank.setCurrentIndex(bank)
 if bank==1:
  w.dataset.setText(str(src.parent/'new_messages'));w.manifest.setText(str(src.parent/'new_messages'/'manifest.json'))
 w.modulation.setCurrentIndex(cl);w.message.setValue(msg);w.frequency.setText(freq);w.gain.setValue(gain);w.real.setChecked(a.transmit);w.duration.setValue(10);w.hold.setValue(1)
 QtTest.QTest.mouseClick(w.start,QtCore.Qt.LeftButton)
 pump_until(lambda:w.run_dir is not None and (w.run_dir/'events.jsonl').exists())
 run=w.run_dir
 pump_until(lambda:any(json.loads(l)['event'] in ('preview','transmitting','error') for l in (run/'events.jsonl').read_text(encoding='utf8').splitlines()))
 w.grab().save(str(run/'started.png'));QtTest.QTest.mouseClick(w.stop,QtCore.Qt.LeftButton)
 pump_until(lambda:not w.running());q.processEvents();w.grab().save(str(run/'stopped.png'))
 result=json.loads((run/'result.json').read_text(encoding='utf8'))
 assert not result['error'] and not result['restore_errors'],result
 if a.transmit:assert len(result['restore_readback'])==5 and all(x['ok'] for x in result['restore_readback'])
 else:assert result['restore_status']=='NOT_APPLICABLE'
 (run/'case.json').write_text(json.dumps(dict(class_index=cl,bank=bank,message=msg,mhz=freq,gain=gain,diagnostic_only=gain<-40,source_sha_file=str(out/'source_sha.json'),physical_ui_verified=False)))
 w.run_dir=None
w.close();print(str(out))
