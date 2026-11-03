#!/usr/bin/env python3
"""Clone the verified release and build only its new UI; never activate or power off."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
BASE=Path('/opt/rml24-integrated/releases/gain_ui_sync_20261102')
DEFAULT_OUT=Path('/opt/rml24-integrated/releases/shutdown_ui_20261102')
PATCHES=['candidate/board_package/board_ui_live_rml24_final.cpp',
         'candidate/board_package/shutdown_action.hpp','candidate/ui_sw/shutdown_ui.hpp',
         'candidate/ui_sw/ui_render.hpp','candidate/ui_sw/ui_render.cpp']
UI='candidate/bin/board_ui_live_rml24_final'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def write_manifest(root):
    lines=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p!=root/'SHA256SUMS.txt':
            lines.append(sha(p)+'  '+p.relative_to(root).as_posix())
    (root/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf8')
def verify_base(base):
    expected=json.loads((ROOT/'BASELINE_FILES.json').read_text(encoding='utf8'))
    actual={p.relative_to(base).as_posix() for p in base.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    if actual!=set(expected): raise RuntimeError('baseline file set changed; recollect before staging')
    for name,digest in expected.items():
        if sha(base/name)!=digest: raise RuntimeError('baseline SHA mismatch: '+name)
    return expected

def verify_external(base):
    receipt=json.loads((base/'PROMOTED_RELEASE.json').read_text())
    for name,digest in receipt['files'].items():
        if Path(name).is_absolute() and sha(name)!=digest:
            raise RuntimeError('external identity mismatch: '+name)

def stage_tree(base,out,compiler):
    verify_base(base)
    if out.exists(): raise RuntimeError('candidate output already exists; preserve it, use a fresh name')
    shutil.copytree(base,out,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    pending=json.loads((out/'PROMOTED_RELEASE.json').read_text())
    pending['all_promotion_gates_passed']=False
    pending['promotion_scope']='UI shutdown staging incomplete; never activate this unfinished directory'
    save(out/'PROMOTED_RELEASE.json',pending)
    for name in PATCHES:
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'release'/name,target)
    compiler(out)
    changed=PATCHES+[UI]
    frozen_path=out/'evidence/CANDIDATE_SOURCE_IDENTITY.json'
    frozen=json.loads(frozen_path.read_text())
    for name in changed: frozen[name]=sha(out/name)
    save(frozen_path,frozen)
    receipt=json.loads((out/'PROMOTED_RELEASE.json').read_text())
    for name in changed+['evidence/CANDIDATE_SOURCE_IDENTITY.json']:
        receipt['files'][name]=sha(out/name)
    receipt.update(all_promotion_gates_passed=False,physical_acceptance_pending=True,
                   promotion_scope='UI-only shutdown candidate; base RF evidence preserved, board acceptance pending')
    save(out/'PROMOTED_RELEASE.json',receipt)
    stage=dict(status='STAGED_BUILD_PASS_NOT_ACTIVATED',base=str(base),candidate=str(out),
               ui_sha256=sha(out/UI),ui_changes=changed,receiver_model_bitstream_service_unchanged=True)
    save(out/'SHUTDOWN_STAGE.json',stage)
    write_manifest(out)
    verify_base(base)
    return stage

def compile_ui(out):
    command=['bash',str(out/'candidate/board_package/build_ui_live_rml24_final.sh')]
    result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False)
    (out/'shutdown_ui_build.log').write_bytes(result.stdout)
    if result.returncode or b'UI_BUILD_RESULT result=PASS' not in result.stdout:
        raise RuntimeError('native UI build failed; original release untouched; see shutdown_ui_build.log')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    if sys.platform!='linux' or os.geteuid()!=0 or platform.machine() not in ('aarch64','arm64'):
        raise RuntimeError('run natively on the aarch64 board as root')
    if Path('/opt/rml24-integrated/current').resolve()!=BASE: raise RuntimeError('current release changed')
    verify_base(BASE);verify_external(BASE)
    if args.check_only: print('SHUTDOWN_BASELINE_CHECK PASS files=224');return
    out=args.out
    if not out.is_absolute() or out.parent.resolve()!=BASE.parent or out.name==BASE.name:
        raise RuntimeError('new candidate must be a distinct release under the existing release directory')
    print(json.dumps(stage_tree(BASE,out,compile_ui),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
