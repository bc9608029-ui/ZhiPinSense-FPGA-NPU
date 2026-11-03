"""Only the two RF rounds expressly approved by the user; never deploys."""
import datetime,hashlib,json,re,subprocess,sys,time
from pathlib import Path
r=Path(__file__).parent;parent=r.parent
serial=parent/'scan_exec_20261027/serial.ps1'
root='/root/rml24_gapfix_execution_20261028'
diag='/root/rml24_mainchain_diagnostic_20261028'
base=root+'/candidate_fix2'
manifest=parent/'rml24_mainchain_diagnostic_20261028/CANDIDATE_FREEZE.json'
def local_check():
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!='69a6775b61a7633bb8c20d0c46ff06e1c01ec3ab76c2757ca2afa82b3db1e6f1':
        raise RuntimeError('Frozen manifest changed')
    for f in json.loads(manifest.read_text())['files']:
        if hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()!=f['sha256']:raise RuntimeError('Frozen source changed '+f['path'])
    oldroot=parent/'rml24_standalone_execution_20261027'
    oldfreeze=json.loads((oldroot/'RF_SOURCE_FREEZE.json').read_text())
    for name in ['autonomous_tx.py','scoring_core.py']:
        if hashlib.sha256((oldroot/name).read_bytes()).hexdigest()!=oldfreeze[name]:raise RuntimeError('Frozen TX/scoring changed '+name)
def board(cmd,seconds=3):
    v=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(serial),
                      '-Command',cmd,'-Seconds',str(seconds)],capture_output=True)
    text=v.stdout.decode(errors='replace')
    with (r/'serial_transcript.log').open('a',encoding='utf-8') as f:f.write(text+'\n')
    if v.returncode:raise RuntimeError(v.stderr.decode(errors='replace'))
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
def status(**v):
    v['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (r/'FIX2_FORMAL_PROGRESS.json').write_text(json.dumps(v,indent=2))
    print(json.dumps(v),flush=True)
def clock(name):
    v=subprocess.run(['powershell','-NoProfile','-File',str(parent/'rml24_standalone_execution_20261027/clock_sync.ps1')],capture_output=True)
    if v.returncode:raise RuntimeError('Clock sync failed')
    data=json.loads(v.stdout.decode(errors='replace'))
    if data['uncertainty_ms']>250:raise RuntimeError('Clock sync uncertainty too large')
    (r/(name+'_clock_before.json')).write_text(json.dumps(data,indent=2))
local_check()
status(phase='preflight',approved=True)
try:
    check=board('python3 '+root+'/preflight_fix2.py')
    if 'BOARD_FROZEN_PREFLIGHT_PASS' not in check.splitlines():raise RuntimeError('Board frozen preflight did not pass: '+check)
    board('systemctl stop rml24-receiver rml24-ui; nohup '+base+'/bin/board_ui_live_rml24_final '+
          '--sock=/run/rml24_mean_validation_ui.sock --ctl-sock=/run/rml24_mean_validation_control.sock '+
          '--control-timeout-ms=35000 --stats-interval=10 --run-id=mean_validation '+
          '> '+root+'/fix2_formal_ui.log 2>&1 & echo VALIDATION_UI_PID=$!')
    for name,mode,hz,hold,duration in [('fix2_fixed01','FIXED',2400000000,4,1120), ('fix2_scan01','BAND_SCAN',2403600000,6,1610)]:
        local_check()
        if 'BOARD_FROZEN_PREFLIGHT_PASS' not in board('python3 '+root+'/preflight_fix2.py').splitlines():raise RuntimeError('Runtime freeze check failed')
        clock(name);run=root+'/'+name
        status(phase='starting_rx',run=name)
        path_check=board('test -e '+run+' && echo RUN_PATH_EXISTS || echo RUN_PATH_CLEAR')
        if 'RUN_PATH_CLEAR' not in path_check.splitlines():raise RuntimeError('Run path not confirmed clear')
        board('nohup env PATH=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin:/usr/bin:/bin '+
              'USER_RF_VALIDATION_APPROVED=YES DURATION_SEC='+str(duration)+' '+
              'UI_SOCKET=/run/rml24_mean_validation_ui.sock UI_CONTROL_SOCKET=/run/rml24_mean_validation_control.sock '+
              'bash '+base+'/rml24_final/board_runtime/run_repeat_mean_gapfix1.sh --run '+run+
              ' --legacy-root /root/amr_rescue_20261025 --model-dir '+
              '/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 --initial-mode '+mode+
              ' > '+root+'/'+name+'.log 2>&1 & echo VALIDATION_RX_PID=$!')
        ready=False
        for _ in range(10):
            text=board('grep -a "^STANDALONE_READY" '+root+'/'+name+'.log; tail -n 2 '+root+'/'+name+'.log')
            if any(v.startswith('STANDALONE_READY no_tcp=1') for v in text.splitlines()):ready=True;break
            time.sleep(1)
        if not ready:raise RuntimeError('RX did not become ready')
        status(phase='transmitting',run=name,completed=0,total=240)
        with (r/(name+'_tx_console.log')).open('wb') as log:
            process=subprocess.Popen([sys.executable,str(parent/'rml24_standalone_execution_20261027/autonomous_tx.py'),
               '--out',str(r/(name+'_tx')),'--mode','formal240','--center-hz',str(hz),
               '--hold-sec',str(hold),'--warmup-sec','40'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            for line in process.stdout:
                log.write(line);log.flush()
                text=line.decode(errors='replace').strip();print(text,flush=True)
                m=re.search(r'TX index=(\d+)',text)
                if m:status(phase='transmitting',run=name,completed=int(m[1]),total=240)
            if process.wait():raise RuntimeError('TX failed')
        status(phase='waiting_for_rx_final',run=name,completed=240,total=240)
        finished=False
        for _ in range(24):
            text=board('test -f '+run+'/capture/final.json && grep -a "^NPU_STREAM_STOP" '+root+'/'+name+'.log')
            if any(v.startswith('NPU_STREAM_STOP frames=') for v in text.splitlines()):finished=True;break
            time.sleep(3)
        if not finished:raise RuntimeError('RX final/stop record missing')
        subprocess.run(['powershell','-NoProfile','-File',str(r/'collect_fix2_formal.ps1')],check=True)
        subprocess.run([sys.executable,str(r/'score_fix2_formal.py'),name],check=True)
        score=json.loads((r/(name+'_score.json')).read_text())
        status(phase='round_complete',run=name,correct=score['correct'],denominator=240,missing=score['missing'])
    local_check();status(phase='fix2_both_formal_rounds_complete_pending_audit')
except BaseException as exc:
    status(phase='error',error=type(exc).__name__+': '+str(exc));raise
finally:
    print(board('python3 '+root+'/cleanup_fix2.py',seconds=7),flush=True)
