from pathlib import Path
import shutil,subprocess
root=Path('/root/rml24_range_expansion_20261101');shutil.copyfile('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/bootcheck.py',root/'bootcheck.py')
Path('/etc/systemd/system/rml24-range-bootcheck.service').write_text('[Unit]\nAfter=rml24-integrated.service\n[Service]\nType=oneshot\nExecStart=/usr/bin/python3 /root/rml24_range_expansion_20261101/bootcheck.py\nStandardOutput=journal+console\nStandardError=journal+console\n[Install]\nWantedBy=multi-user.target\n')
subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','enable','rml24-range-bootcheck'],check=True);subprocess.run(['sync'],check=True);print('BOOTCHECK_ARMED',flush=True)
