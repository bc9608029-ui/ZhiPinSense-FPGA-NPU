from pathlib import Path
import hashlib,json,shutil
old=Path('F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1')
new=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030')
here=Path(__file__).parent
if new.exists():raise RuntimeError('refuse existing clone')
if shutil.disk_usage('F:/').free<10*1024**3:raise RuntimeError('less than 10 GiB free on F')
new.mkdir();copied=0;changed=[]
def skip(p):
    return any(s.endswith(('.runs','.cache','.sim','.hw')) or s in ['.Xil','ip_user_files','__pycache__'] for s in p.parts)
for p in (old/'fpga').rglob('*'):
    if not p.is_file() or skip(p.relative_to(old)):continue
    q=new/p.relative_to(old);q.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(p,q);copied+=1
    if p.suffix.lower() in ['.tcl','.xpr','.xdc','.xci','.xml','.prj','.bd','.bat']:
        try:s=q.read_text(encoding='utf-8')
        except UnicodeError:continue
        t=s.replace(old.as_posix(),new.as_posix()).replace(str(old),str(new))
        if t!=s:q.write_text(t,encoding='utf-8');changed.append(str(q.relative_to(new)))
target=new/'fpga/smartscan_integration/rtl/smart_scan_psd_buffers.sv'
before=hashlib.sha256(target.read_bytes()).hexdigest()
expected=json.loads((here/'IDENTITY.json').read_text())['original_sha256']
if before!=expected:raise RuntimeError('base BRAM source drift')
shutil.copyfile(here/'smart_scan_psd_buffers.sv',target)
(new/'reports').mkdir();(new/'build').mkdir()
m3=new/'fpga/m3_synth_smartscan.tcl'
s=m3.read_text(encoding='utf-8')
s=s.replace('launch_runs synth_1 -jobs 1','''# Fresh clone has no OOC run products: regenerate every IP, do not trust old statuses.
foreach ip_run [get_runs -quiet *_synth_1] {reset_run $ip_run}
launch_runs synth_1 -jobs 1''')
m3.write_text(s,encoding='utf-8')
(new/'CLONE_IDENTITY.json').write_text(json.dumps(dict(original=str(old),candidate=str(new),copied=copied,
    changed_paths=changed,buffer_before=before,buffer_after=hashlib.sha256(target.read_bytes()).hexdigest()),indent=2))
print('CLONE_READY',new,'files',copied)
