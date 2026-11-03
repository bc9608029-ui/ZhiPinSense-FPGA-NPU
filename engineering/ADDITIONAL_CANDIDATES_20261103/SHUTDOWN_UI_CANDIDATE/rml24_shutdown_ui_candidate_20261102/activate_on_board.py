#!/usr/bin/env python3
"""Activate or roll back an isolated UI-only candidate after board dry-run proof."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from stage_on_board import BASE, DEFAULT_OUT, verify_base, verify_external, sha, save, write_manifest

CURRENT=Path('/opt/rml24-integrated/current')
UNIT='rml24-integrated.service'
GUARD=Path('/var/lib/rml24-fpga-shared-guard/reset_required.json')

def stop_clean():
    subprocess.run(['systemctl','stop',UNIT],check=True,timeout=130)
    result=subprocess.run(['systemctl','show',UNIT,'--property=ActiveState,MainPID'],
                          check=True,stdout=subprocess.PIPE,universal_newlines=True)
    values=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    if values.get('ActiveState')!='inactive' or values.get('MainPID')!='0':
        raise RuntimeError('service not fully stopped; leave current pointer unchanged')
    if GUARD.exists():
        raise RuntimeError('hardware guard retained: stop here; never clear it manually; reboot/review required')

def switch(target):
    temp=CURRENT.parent/('.current.shutdown.'+str(os.getpid()))
    if temp.exists() or temp.is_symlink(): raise RuntimeError('unexpected temporary symlink exists')
    os.symlink(str(target),str(temp));os.replace(str(temp),str(CURRENT))
    os.sync()

def verify_candidate(candidate):
    stage=json.loads((candidate/'SHUTDOWN_STAGE.json').read_text())
    if stage['status']!='STAGED_BUILD_PASS_NOT_ACTIVATED' or sha(candidate/'candidate/bin/board_ui_live_rml24_final')!=stage['ui_sha256']:
        raise RuntimeError('candidate build identity changed')
    frozen=json.loads((candidate/'evidence/CANDIDATE_SOURCE_IDENTITY.json').read_text())
    for name,digest in frozen.items():
        if sha(candidate/name)!=digest: raise RuntimeError('candidate source changed: '+name)
    receipt=json.loads((candidate/'PROMOTED_RELEASE.json').read_text())
    for name,digest in receipt['files'].items():
        if sha(Path(name) if Path(name).is_absolute() else candidate/name)!=digest:
            raise RuntimeError('candidate receipt mismatch: '+name)
    return receipt

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,default=DEFAULT_OUT)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--dry-run-log',type=Path);g.add_argument('--rollback',action='store_true')
    a=p.parse_args()
    if sys.platform!='linux' or os.geteuid()!=0:raise RuntimeError('board root required')
    candidate=a.candidate.resolve()
    if candidate.parent!=BASE.parent or candidate==BASE:raise RuntimeError('unexpected candidate directory')
    verify_base(BASE);verify_external(BASE)
    if a.rollback:
        if CURRENT.resolve()!=candidate:raise RuntimeError('current pointer is not this candidate')
        stop_clean();switch(BASE);subprocess.run(['systemctl','start',UNIT],check=True)
        print('SHUTDOWN_UI_ROLLBACK_STARTED; inspect service readiness; no forced reset')
        return
    if CURRENT.resolve()!=BASE:raise RuntimeError('base current pointer changed')
    receipt=verify_candidate(candidate)
    data=a.dry_run_log.read_text(errors='replace')
    required=['UI_SHUTDOWN_FEATURE version=shutdown_ui_20261102 dry_run=YES',
              'UI_FB_READY','UI_VERSION_CHECK','ok=YES','UI_SHUTDOWN_RESULT result=DRY_RUN','UI_LIVE_STOP']
    if any(text not in data for text in required):raise RuntimeError('incomplete board UI dry-run log')
    stop_clean()
    receipt.update(all_promotion_gates_passed=True,physical_acceptance_pending=True,
                   promotion_scope='UI-only shutdown: native build and board dry-run accepted; live poweroff/reboot acceptance pending',
                   shutdown_ui_dry_run_log_sha256=hashlib.sha256(data.encode()).hexdigest())
    save(candidate/'PROMOTED_RELEASE.json',receipt)
    save(candidate/'SHUTDOWN_ACTIVATION.json',dict(previous_release=str(BASE),
         ui_sha256=sha(candidate/'candidate/bin/board_ui_live_rml24_final'),
         actual_poweroff_test_passed=False,time_ns=time.time_ns()))
    write_manifest(candidate)
    switch(candidate)
    try:subprocess.run(['systemctl','start',UNIT],check=True)
    except Exception:
        switch(BASE)
        # A failed hardware start can leave the guard set. Do not force a restart.
        if not GUARD.exists():subprocess.run(['systemctl','start',UNIT],check=False)
        raise
    print('SHUTDOWN_UI_ACTIVATION_STARTED; verify UI/NPU/RX readiness and live poweroff; not RF_PASS')

if __name__=='__main__':main()
