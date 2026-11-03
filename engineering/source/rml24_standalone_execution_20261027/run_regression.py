"""Bounded independent-RF regressions; preserves existing services and model."""
import json,subprocess,sys,time
from pathlib import Path
r=Path(__file__).parent
serial=r.parent/'scan_exec_20261027/serial.ps1'
def board(command):
    done=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(serial),
                         '-Command',command,'-Seconds','3'],capture_output=True)
    print(done.stdout.decode(errors='replace'),flush=True)
    if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace'))
root='/root/rml24_standalone_execution_20261027'
for name,mode,hz,hold,duration in [('formal_fixed01','FIXED',2400000000,4,1120),
                                  ('formal_scan01','BAND_SCAN',2403600000,6,1610)]:
    run=root+'/'+name
    command=('cd '+root+'/candidate; '+
      'if test -e '+run+'; then echo REFUSE_EXISTING_RUN; else '+
      'nohup env PATH=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin:/usr/bin:/bin '+
      'DURATION_SEC='+str(duration)+' UI_SOCKET=/run/rml24_standalone_ui.sock '+
      'UI_CONTROL_SOCKET=/run/rml24_standalone_control.sock bash rml24_final/board_runtime/run_standalone.sh '+
      '--run '+run+' --legacy-root /root/amr_rescue_20261025 '+
      '--model-dir /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 '+
      '--initial-mode '+mode+' > '+root+'/'+name+'.log 2>&1 & echo RX_PID=$!; fi')
    print('REGRESSION_START '+name,flush=True);board(command)
    t0=time.monotonic()
    with (r/(name+'_tx_console.log')).open('wb') as log:
        process=subprocess.Popen([sys.executable,str(r/'autonomous_tx.py'),'--out',str(r/(name+'_tx')),
                   '--mode','formal240','--center-hz',str(hz),'--hold-sec',str(hold),'--warmup-sec','40'],
                   stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        for line in process.stdout:
            log.write(line);log.flush();print(line.decode(errors='replace').rstrip(),flush=True)
        if process.wait():raise RuntimeError('TX regression failed: '+name)
    remaining=duration-(time.monotonic()-t0)+3
    print('WAIT_RX_FINAL seconds='+str(max(0,round(remaining))),flush=True)
    if remaining>0:time.sleep(remaining)
    board('tail -n 4 '+root+'/'+name+'.log; cat '+run+'/capture/final.json')
    completed=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(r/'collect_evidence.ps1')])
    completed.check_returncode()
    score=subprocess.run([sys.executable,str(r/'score_independent.py'),name]);score.check_returncode()
    result=json.loads((r/(name+'_score.json')).read_text())
    print('REGRESSION_SCORE %s %d/%d missing=%d'%(name,result['correct'],result['denominator'],result['missing']),flush=True)
print('REGRESSION_BOTH_COMPLETE',flush=True)
