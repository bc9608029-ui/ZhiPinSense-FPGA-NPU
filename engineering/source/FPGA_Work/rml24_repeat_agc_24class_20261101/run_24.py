import subprocess
from pathlib import Path
base=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031')
try:
 subprocess.run(['systemctl','stop','rml24-integrated'],check=True)
 subprocess.run(['/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3',str(base/'capture_24.py')],check=True)
finally:
 subprocess.run(['systemctl','start','rml24-integrated'],check=True)
print('ORIGINAL_SERVICE_RESTORED',flush=True)
