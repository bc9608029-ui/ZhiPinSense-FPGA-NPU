from pathlib import Path
import shutil,hashlib,json
r=Path(__file__).parent
base=Path('F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga')
prep=Path('F:/嵌赛/rml24_fpga_smartscan_prep2_20261028')
work=r/'pspl_regression';work.mkdir(exist_ok=False)
records={}
def copy(p,name=None):
    q=work/(name or p.name);shutil.copyfile(p,q)
    records[q.name]={'source':str(p),'sha256':hashlib.sha256(q.read_bytes()).hexdigest()}
for p in (base/'smartscan_integration/rtl').glob('*'):
    if p.suffix in ['.v','.sv'] and p.name not in ['pl_ddr_mandatory_core_top_combined_smartscan.sv','user_reg_router.sv','user_ddr_read_arbiter.sv']:
        copy(p)
copy(r/'smart_scan_psd_buffers.sv')
for name in ['async_fifo_gray.sv','iq_beat_unpacker.sv','pl_ddr_iq_input_adapter.sv','user_ddr_iq_reader.sv','job_domain_controller.sv','fft_magnitude_square_u54.sv']:
    matches=[p for p in base.rglob(name) if 'ip_patch' not in p.parts]
    if not matches:matches=list(prep.rglob(name))
    unique={hashlib.sha256(p.read_bytes()).hexdigest() for p in matches}
    if len(unique)!=1:raise RuntimeError('ambiguous dependency '+name+' '+str(matches))
    copy(matches[0])
copy(prep/'tb/tb_smart_scan_pspl.sv')
copy(base/'smartscan_integration/xfft_z030/work_build/smartscan_fft_z030.srcs/sources_1/ip/smartscan_fft_1024/smartscan_fft_1024_sim_netlist.v')
copy(Path('D:/Xilinx2018.3/Vivado/2018.3/data/verilog/src/glbl.v'))
(work/'SOURCE_IDENTITY.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(work/'run.ps1').write_text('''$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$env:TEMP=$PSScriptRoot
$env:TMP=$PSScriptRoot
$Bin='D:\\Xilinx2018.3\\Vivado\\2018.3\\bin'
& "$Bin\\xvlog.bat" glbl.v smartscan_fft_1024_sim_netlist.v hann_coeff_rom.v
if($LASTEXITCODE -ne 0){throw 'Verilog compile failed'}
$Sources=Get-ChildItem -LiteralPath . -Filter '*.sv' | ForEach-Object {$_.Name}
& "$Bin\\xvlog.bat" --sv @Sources
if($LASTEXITCODE -ne 0){throw 'SV compile failed'}
& "$Bin\\xelab.bat" --relax -mt 2 -L unisims_ver -L unimacro_ver -L secureip -s pspl_fixed tb_smart_scan_pspl glbl
if($LASTEXITCODE -ne 0){throw 'elaboration failed'}
& "$Bin\\xsim.bat" pspl_fixed -runall
if($LASTEXITCODE -ne 0){throw 'simulation failed'}
''',encoding='utf-8')
print('PSPL_REGRESSION_PREPARED',len(records))
