$ErrorActionPreference='Stop'
$Tools='D:\Xilinx2018.3\Vivado\2018.3\bin'
$env:TEMP=$PSScriptRoot
$env:TMP=$PSScriptRoot
Set-Location $PSScriptRoot
& "$Tools\xvlog.bat" --sv smart_scan_psd_buffers.sv tb_buffers.sv
if($LASTEXITCODE -ne 0){throw 'xvlog failed'}
& "$Tools\xelab.bat" tb_buffers -s bram_fix_sim
if($LASTEXITCODE -ne 0){throw 'xelab failed'}
& "$Tools\xsim.bat" bram_fix_sim -runall
if($LASTEXITCODE -ne 0){throw 'xsim failed'}
