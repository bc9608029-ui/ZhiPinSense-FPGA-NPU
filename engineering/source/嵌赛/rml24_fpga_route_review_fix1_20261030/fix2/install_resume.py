from pathlib import Path
import shutil
HERE=Path(__file__).resolve().parent
ROOT=Path('F:/FPGA_Work/smartscan_bram_fix1_20261030')
if (ROOT/'build/pipeline.lock').exists():raise RuntimeError('ACTIVE_OR_STALE_LOCK_REQUIRES_REVIEW')
shutil.copy2(HERE/'resume_guarded.tcl',ROOT/'fpga/resume_fix2.tcl')
text=(ROOT/'build/pipeline_fix2.py').read_text(encoding='utf-8')
old="[('m3_synth_smartscan.tcl','synthesis'),('implement_fix2.tcl','implementation')]"
assert old in text
text=text.replace(old,"[('resume_fix2.tcl','implementation_resume')]")
(ROOT/'build/pipeline_resume2.py').write_text(text,encoding='utf-8')
start=(HERE.parent/'start_pipeline.ps1').read_text(encoding='utf-8')
start=start.replace('pipeline_fix1.py','pipeline_resume2.py').replace('supervisor.log','supervisor_resume2.log').replace('supervisor.rc','supervisor_resume2.rc')
(ROOT/'build/start_resume2.ps1').write_text(start,encoding='utf-8')
print('RESUME_INSTALLED')
