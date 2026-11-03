from pathlib import Path
import shutil,subprocess
r=Path('/root/rml24_final_install_20261031');e=Path('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031')
shutil.copyfile(e/'PC_PL_PROGRAM_VERIFIED.json',r/'PC_PL_PROGRAM_VERIFIED.json')
subprocess.run(['python3',str(e/'deployment_files/install_release.py'),'activate'],check=True)
