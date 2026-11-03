$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$env:TEMP=$PSScriptRoot
$env:TMP=$PSScriptRoot
$Bin='D:\Xilinx2018.3\Vivado\2018.3\bin'
& "$Bin\xvlog.bat" glbl.v smartscan_fft_1024_sim_netlist.v hann_coeff_rom.v
if($LASTEXITCODE -ne 0){throw 'Verilog compile failed'}
$Sources=Get-ChildItem -LiteralPath . -Filter '*.sv' | ForEach-Object {$_.Name}
& "$Bin\xvlog.bat" --sv @Sources
if($LASTEXITCODE -ne 0){throw 'SV compile failed'}
& "$Bin\xelab.bat" --relax -mt 2 -L unisims_ver -L unimacro_ver -L secureip -s pspl_fixed tb_smart_scan_pspl glbl
if($LASTEXITCODE -ne 0){throw 'elaboration failed'}
& "$Bin\xsim.bat" pspl_fixed -runall
if($LASTEXITCODE -ne 0){throw 'simulation failed'}
