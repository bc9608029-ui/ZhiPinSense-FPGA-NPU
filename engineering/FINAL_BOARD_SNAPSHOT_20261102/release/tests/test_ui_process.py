"""Linux host C++ UI real socket/parser/history integration; no FPGA/SDR."""
import json,os,socket,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='rml_history_',dir='/tmp') as temp:
    run=Path(temp);sock=run/'ui.sock';hist=run/'history.txt';log=run/'ui.log'
    with log.open('wb') as f:
        child=subprocess.Popen([str(ROOT/'candidate/bin/board_ui_live_rml24_final'),
            '--headless','--no-touch','--sock='+str(sock),'--ctl-sock='+str(run/'none.sock'),
            '--history-file='+str(hist),'--model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'],stdout=f,stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if sock.exists():break
                if child.poll() is not None:raise RuntimeError(log.read_text())
                time.sleep(.05)
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
                c.connect(str(sock))
                for line in (ROOT/'evidence/gui_frames.jsonl').read_text().splitlines():
                    c.sendall((line+'\n').encode());time.sleep(.04)
                c.sendall((json.dumps(dict(type='state',version='rml24-standalone-state-v1',command_id=1,
                    work_mode='CONTINUOUS_SCAN',run_state='RUNNING',presence_state='ACQUIRING',timestamp_us=100,
                    model_sha='c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'))+'\n').encode())
                time.sleep(.2)
        finally:
            child.terminate();child.wait(timeout=5)
    text=log.read_text()
    assert 'valid=12 rejected=0' in text,text
    assert 'UI_RX type=state version=rml24-standalone-state-v1 valid=1' in text,text
    assert len(hist.read_text().splitlines())==11,hist.read_text()
    (ROOT/'evidence/ui_process.log').write_text(text)
    (ROOT/'evidence/ui_process_history.txt').write_text(hist.read_text())
    print('UI_PROCESS_HISTORY PASS results=12 history=10 state_mode=CONTINUOUS_SCAN')
