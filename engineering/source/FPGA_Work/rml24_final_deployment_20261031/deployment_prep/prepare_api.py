from pathlib import Path
import shutil,json,subprocess
r=Path('/root/rml24_final_install_20261031');e=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/deployment_files')
for n in ('board_acceptance_server.py','rollback_release.py'):shutil.copyfile(e/n,r/n)
(r/'ACCEPTANCE_CONFIG.json').write_text(json.dumps({"token": "REDACTED_LOCAL_ACCESS_TOKEN_SET_AT_RUNTIME"}))
subprocess.run(['systemctl','stop','rml24-ui','rml24-receiver'],check=True)
for args in (['pgrep','-x','npu_stream'],['pgrep','-f','^/root/rml24_fpga_shared_owner_20261031/build/npu_stream_shared']):assert subprocess.run(args).returncode==1
assert not Path('/var/lib/rml24-fpga-shared-guard/reset_required.json').exists()
print('OWNERS_STOPPED_BOOT_ID='+Path('/proc/sys/kernel/random/boot_id').read_text().strip(),flush=True)
subprocess.Popen(['python3',str(r/'board_acceptance_server.py'),'--staging','--seconds','900'],stdout=(r/'staging_api.log').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
