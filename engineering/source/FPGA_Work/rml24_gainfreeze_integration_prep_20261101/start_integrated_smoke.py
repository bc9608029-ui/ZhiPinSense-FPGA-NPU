from pathlib import Path
import subprocess
r=Path('/root/rml24_gainfreeze_integration_20261101');src=r/'candidate';assert (r/'CANDIDATE_READY.json').exists()
subprocess.run(['systemctl','stop','rml24-integrated'],check=True)
for args in [['pgrep','-x','npu_stream'],['pgrep','-f','^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared']]:assert subprocess.run(args).returncode==1
assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
cmd=['systemd-run','--unit=rml24-gainfreeze-integrated-smoke','--property=KillMode=mixed','--property=SendSIGKILL=no','--property=TimeoutStopSec=120','--setenv=HOME=/root','--setenv=PATH=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3',str(src/'scripts/run_candidate_finalize_v2.py'),'--legacy-root','/root/amr_rescue_20261025','--model-dir','/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16','--npu-sha','cc88cb0bf5cde766937d011978314b7dafd1122d0f18e1cbda731ec2f7a440d8','--run',str(r/'smoke_run'),'--mode','FIXED','--duration-sec','900','--history-file',str(r/'smoke_history.txt')];subprocess.run(cmd,check=True);print('INTEGRATED_SMOKE_STARTED',flush=True)
