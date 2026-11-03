#!/usr/bin/env python3
"""Linux foreground supervisor. No RF TX, no service or bitstream changes.

All SDR access occurs only after explicit --run. --check is read-only preflight.
Only our live child handles are stopped, RX first. No external PID killing.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
MODEL={'rml24_adamrv11_bf16.json':'28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42',
       'rml24_adamrv11_bf16.raw':'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151'}
LEGACY={'pluto_link_probe.py':'1b248f8f391976513c35ca54f31d7daef3fa363e2d095940f9ff17d4d60126a2',
        'pilot_recovery.py':'d7538a1e27b65cd6b712607b485f1e07de447467bbfdbb04ce67143f9d797713'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def preflight(a):
    frozen=json.loads((ROOT/'evidence/CANDIDATE_SOURCE_IDENTITY.json').read_text())
    for rel,digest in frozen.items():
        if sha(ROOT/rel)!=digest:raise RuntimeError('candidate SHA mismatch '+rel)
    for directory,expected in [(a.model_dir,MODEL),(a.legacy_root,LEGACY)]:
        for name,digest in expected.items():
            if sha(directory/name)!=digest:raise RuntimeError('external SHA mismatch '+str(directory/name))
    npu=a.legacy_root/'build/npu_stream'
    ui=ROOT/'candidate/bin/board_ui_live_rml24_final'
    for p in [npu,ui]:
        if not p.is_file() or not os.access(str(p),os.X_OK):raise RuntimeError('missing executable '+str(p))
    # NPU executable must be independently matched to the installed stable binary.
    if len(a.npu_sha)!=64 or sha(npu)!=a.npu_sha.lower():raise RuntimeError('NPU executable identity mismatch')
    subprocess.run([sys.executable,'-c','import numpy, scipy'],check=True)
    print('SWEEP_HISTORY_PREFLIGHT PASS',flush=True)

def socket_ready(p):
    try:return stat.S_ISSOCK(p.stat().st_mode)
    except FileNotFoundError:return False

def wait_ready(child,path,log,marker,seconds=30):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if child.poll() is not None:raise RuntimeError('child exited before ready: '+str(log))
        if socket_ready(path) and (not marker or marker in log.read_text(errors='replace')):return
        time.sleep(.1)
    raise RuntimeError('readiness timeout '+str(log))

def stop_children(children,timeout=40):
    errors=[]
    for role,p in reversed(children):
        if p.poll() is None:
            p.terminate()
            try:p.wait(timeout=timeout if role=='rx' else 10)
            except subprocess.TimeoutExpired:
                errors.append(role+' stop timeout (not force-killed)')
                # Preserve NPU/UI while RX still owns the SDR and may be restoring.
                if role=='rx':break
    return errors

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--legacy-root',type=Path,required=True);p.add_argument('--model-dir',type=Path,required=True)
    p.add_argument('--npu-sha',required=True,help='trusted stable npu_stream SHA, independently checked')
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--check',action='store_true');g.add_argument('--run',type=Path)
    p.add_argument('--mode',choices=['FIXED','BAND_SCAN','CONTINUOUS_SCAN'],default='FIXED')
    p.add_argument('--fixed-hz',type=int,default=2400000000)
    p.add_argument('--scan-start-hz',type=int,default=2395000000);p.add_argument('--scan-stop-hz',type=int,default=2405000000)
    p.add_argument('--scan-step-hz',type=int,default=1000000);p.add_argument('--duration-sec',type=float,default=60)
    p.add_argument('--history-file',type=Path,help='persistent candidate history; never share with a live UI')
    p.add_argument('--save-captures',action='store_true')
    a=p.parse_args()
    if a.duration_sec<=0:raise ValueError('positive duration required')
    sys.path.insert(0,str(ROOT/'candidate/rml24_final/runtime'))
    from standalone_control import Controller
    Controller(a.fixed_hz,a.scan_start_hz,a.scan_stop_hz,a.scan_step_hz,2300000000,2500000000)
    preflight(a)
    if a.check:return 0
    if sys.platform!='linux':raise RuntimeError('board execution requires Linux')
    for unit in ['rml24-ui','rml24-receiver']:
        if subprocess.run(['systemctl','is-active','--quiet',unit]).returncode==0:
            raise RuntimeError('stop the stable service explicitly before testing: '+unit)
    run=a.run
    if not run.is_absolute():raise ValueError('absolute fresh RUN required')
    for name in ['npu.sock','ui.sock','control.sock']:
        if len(os.fsencode(str(run/name)))>100:raise ValueError('Unix socket path too long')
    run.mkdir(exist_ok=False)
    children=[];logs=[];result={'mode':a.mode,'rf_tx':False,'candidate_only':True}
    history_lock=None
    stopping=[False]
    for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:stopping.__setitem__(0,True))
    def spawn(role,cmd):
        f=(run/(role+'.log')).open('wb');logs.append(f)
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        child=subprocess.Popen(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,env=env)
        children.append((role,child))
        (run/'children.json').write_text(json.dumps([{'role':r,'pid':c.pid,'argv':c.args} for r,c in children],indent=2))
        return child
    try:
        if sha(Path('/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared'))!='7b185cad8aaf526344a36666a90071e59577a2fa1488a7f8f0523ce437bc0af9':raise RuntimeError('shared worker identity mismatch')
        npu=spawn('npu',[sys.executable,ROOT/'scripts/hardware_restart_guard.py','--state-dir','/var/lib/rml24-fpga-shared-guard',Path('/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared'),a.model_dir/'rml24_adamrv11_bf16.json',a.model_dir/'rml24_adamrv11_bf16.raw',run/'npu.sock'])
        wait_ready(npu,run/'npu.sock',run/'npu.log','')
        hist=a.history_file or run/'history.txt'
        if not hist.is_absolute() or not hist.parent.is_dir():raise ValueError('absolute history path with existing parent required')
        import fcntl
        history_lock=Path(str(hist)+'.lock').open('a')
        fcntl.flock(history_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        ui=spawn('ui',[ROOT/'candidate/bin/board_ui_live_rml24_final','--sock='+str(run/'ui.sock'),
            '--ctl-sock='+str(run/'control.sock'),'--history-file='+str(hist),
            '--model-sha='+MODEL['rml24_adamrv11_bf16.raw'],'--run-id='+run.name])
        wait_ready(ui,run/'ui.sock',run/'ui.log','UI_FB_READY')
        cmd=[sys.executable,ROOT/'candidate/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py',
            '--legacy-root',a.legacy_root,'--npu-socket',run/'npu.sock','--ui-socket',run/'ui.sock',
            '--ui-control-socket',run/'control.sock','--out',run/'capture','--initial-mode',a.mode,
            '--fixed-center-hz',a.fixed_hz,'--scan-start-hz',a.scan_start_hz,'--scan-stop-hz',a.scan_stop_hz,
            '--scan-step-hz',a.scan_step_hz,'--duration-sec',a.duration_sec]
        cmd += ['--spectrum-backend','fpga','--spectrum-driver','/root/rml24_fpga_diag_1793380588/scan_xrt']
        if a.save_captures:cmd.append('--save-captures')
        rx=spawn('rx',cmd);wait_ready(rx,run/'control.sock',run/'rx.log','STANDALONE_READY')
        print('SWEEP_HISTORY_RUNNING run='+str(run),flush=True)
        while rx.poll() is None and not stopping[0]:
            if ui.poll() is not None:raise RuntimeError('UI exited unexpectedly')
            if npu.poll() is not None:
                # Normal RX EOF can stop NPU just before RX writes final files.
                if npu.returncode != 0:raise RuntimeError('NPU failed rc='+str(npu.returncode))
                try:rx.wait(timeout=40.0)
                except subprocess.TimeoutExpired:raise RuntimeError('NPU exited while RX remained active')
                if rx.returncode != 0:raise RuntimeError('RX failed after NPU EOF')
                if 'NPU_STREAM_STOP' not in (run/'npu.log').read_text(errors='replace'):raise RuntimeError('Missing NPU stop accounting')
                final=json.loads((run/'capture/final.json').read_text())
                restored=json.loads((run/'capture/restore.json').read_text())
                accounting=re.search(r'NPU_STREAM_STOP frames=(\d+) apply=(\d+) reset=(\d+) discipline=(\d+)',(run/'npu.log').read_text(errors='replace'))
                if ui.poll() is not None:raise RuntimeError('UI exited during RX finalization')
                if restored or final['restore_errors']:raise RuntimeError('RX restore failed')
                frames=final['valid']*8
                if not accounting or tuple(map(int,accounting.groups()))!=(frames,1,max(0,frames-1),1):raise RuntimeError('NPU final accounting mismatch')
                result['normal_npu_eof_before_rx_reap']=True
                result['finalization_accounting_verified']=True
                break
            time.sleep(.1)
        if rx.poll() not in [None,0]:raise RuntimeError('RX failed rc='+str(rx.returncode))
    except Exception as exc:
        result['error']=str(exc)
    finally:
        result['stop_errors']=stop_children(children)
        if any(role=='npu' and child.poll()==78 for role,child in children):
            result['hardware_reset_required']=True;result['error']='Hardware guard blocked restart; full board reboot required'
        for f in logs:f.close()
        if history_lock:history_lock.close()
        restore=run/'capture/restore.json'
        result['rx_restore']=json.loads(restore.read_text()) if restore.is_file() else None
        result['clean_stop']=not result.get('error') and not result['stop_errors'] and result['rx_restore']==[]
        (run/'supervisor.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result),flush=True)
    return 78 if result.get('hardware_reset_required') else (0 if result['clean_stop'] else 1)

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:print('SWEEP_HISTORY_FAIL '+str(exc),file=sys.stderr);sys.exit(1)
