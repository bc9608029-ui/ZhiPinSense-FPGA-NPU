from pathlib import Path
import shutil, hashlib, json, datetime
HERE=Path(__file__).resolve().parent
ROOT=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030')
lock=ROOT/'build/pipeline.lock'
if lock.exists():
    import subprocess
    pid=int(lock.read_text())
    probe=subprocess.run(['powershell.exe','-NoProfile','-Command',f'Get-Process -Id {pid} -ErrorAction SilentlyContinue'],capture_output=True)
    if probe.returncode==0:raise RuntimeError(f'LIVE_SUPERVISOR_LOCK {pid}')
    lock.unlink()
for name,rel in [('user_reg_router','smartscan_integration/rtl/user_reg_router.sv'),('user_ddr_read_arbiter','smartscan_integration/rtl/user_ddr_read_arbiter.sv'),('async_fifo_gray','pl_ddr_integration_v1/deps/adapters/async_fifo_gray.sv')]:
    # Compare normalized text: no hidden concurrent source edits are accepted.
    if (ROOT/'fpga'/rel).read_text(encoding='utf-8') not in [(HERE/f'{name}_original.sv').read_text(encoding='utf-8'),(HERE/f'{name}.sv').read_text(encoding='utf-8')]:
        raise RuntimeError('ORIGINAL_SOURCE_DRIFT '+name)
backup=HERE/'prior_build_evidence'; backup.mkdir(exist_ok=True)
for directory in [ROOT/'build', ROOT/'fpga/npu_base/fpai_demo_vivado.runs/impl_1']:
    out=backup/directory.name
    if out.exists():continue
    out.mkdir()
    for p in directory.iterdir():
        if p.is_file() and p.suffix in {'.log','.json','.rpt','.dcp','.rc'}:
            shutil.copy2(p,out/p.name)
changes={
 'user_reg_router.sv':'smartscan_integration/rtl/user_reg_router.sv',
 'pl_ddr_mandatory_core_top_combined_smartscan.sv':'smartscan_integration/rtl/pl_ddr_mandatory_core_top_combined_smartscan.sv',
 'user_ddr_read_arbiter.sv':'smartscan_integration/rtl/user_ddr_read_arbiter.sv',
 'async_fifo_gray.sv':'pl_ddr_integration_v1/deps/adapters/async_fifo_gray.sv',
}
records=[]
for name,rel in changes.items():
    dest=ROOT/'fpga'/rel
    if not (backup/name).exists():shutil.copy2(dest,backup/name)
    old=hashlib.sha256((backup/name).read_bytes()).hexdigest()
    shutil.copy2(HERE/name,dest)
    records.append(dict(path=rel,before=old,after=hashlib.sha256(dest.read_bytes()).hexdigest()))
tcl=ROOT/'fpga/m3_synth_smartscan.tcl'
if not (backup/tcl.name).exists():shutil.copy2(tcl,backup/tcl.name)
text=(backup/tcl.name).read_text(encoding='utf-8')
start=text.index('if {[get_runs -quiet ps_ai_processing_system7_0_0_synth_1]')
end=text.index('launch_runs synth_1 -jobs 1', start)
text=text[:start]+'# OOC IP products are already built and unchanged. Reset top synthesis only.\nreset_run synth_1\n'+text[end:]
tcl.write_text(text,encoding='utf-8')
shutil.copy2(HERE/'implement_guarded.tcl',ROOT/'fpga/implement_fix2.tcl')
pipeline=(HERE.parent/'pipeline_fix1.py').read_text(encoding='utf-8')
pipeline=pipeline.replace("('implement_fix1.tcl','implementation')", "('implement_fix2.tcl','implementation')")
pipeline=pipeline.replace("'FIX1_ROUTED_REPORTS_READY_NO_BITSTREAM'", "'FIX2_ROUTED_REPORTS_READY_NO_BITSTREAM'")
pipeline=pipeline.replace("stage+'.stdout.log'", "stage+'_fix2.stdout.log'")
pipeline=pipeline.replace("stage+'.log'", "stage+'_fix2.log'").replace("stage+'.jou'", "stage+'_fix2.jou'")
gates=[(str(HERE/'tb_router.log'),'ROUTER_TEST_PASS'),
       (str(HERE/'tb_fifo.log'),'ALL_FIFO_CASES_PASS'),
       (str(HERE/'tb_arbiter.log'),'DDR_ARBITER_PASS'),
       (str(HERE/'routed_pspl/xsim.log'),'TB_SMART_SCAN_PSPL PASS cases=3 faults=2'),
       (str(HERE/'shared_pspl/xsim_retry.log'),'TB_SMART_SCAN_PSPL PASS cases=3 faults=2')]
precheck='''        deadline=time.monotonic()+1200
        gates=GATE_LIST
        while True:
            pending=[p for p,marker in gates if not Path(p).exists() or marker not in Path(p).read_text(errors='replace')]
            if not pending:break
            if time.monotonic()>deadline:raise RuntimeError('OFFLINE_GATE_TIMEOUT '+str(pending))
            status(state='WAITING_OFFLINE_GATES',pending=pending,revision='fix2');time.sleep(10)
'''.replace('GATE_LIST',repr(gates))
pipeline=pipeline.replace('    try:\n        for script', '    try:\n'+precheck+'        for script')
(ROOT/'build/pipeline_fix2.py').write_text(pipeline,encoding='utf-8')
start=(HERE.parent/'start_pipeline.ps1').read_text(encoding='utf-8').replace('pipeline_fix1.py','pipeline_fix2.py').replace('supervisor.log','supervisor_fix2.log').replace('supervisor.rc','supervisor_fix2.rc')
(ROOT/'build/start_pipeline_fix2.ps1').write_text(start,encoding='utf-8')
(ROOT/'REVISION_FIX2.json').write_text(json.dumps({'time':datetime.datetime.now().isoformat(),'changes':records,'board_touched':False,'bitstream_generated':False},indent=2))
print('INDEPENDENT_FIX2_APPLIED',json.dumps(records))
