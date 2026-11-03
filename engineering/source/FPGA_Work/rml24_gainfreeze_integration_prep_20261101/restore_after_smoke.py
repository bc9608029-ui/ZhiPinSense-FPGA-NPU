import subprocess,time
subprocess.run(['systemctl','stop','rml24-gainfreeze-integrated-smoke'],check=True)
subprocess.run(['systemctl','start','rml24-integrated'],check=True);time.sleep(8)
subprocess.run(['python3','/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/live_status.py'],check=True)
