$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$env:TEMP=$PSScriptRoot; $env:TMP=$PSScriptRoot
$bin='D:\Xilinx2018.3\Vivado\2018.3\bin'
$orig=Get-Content -Raw async_fifo_gray_original.sv
$orig.Replace('module async_fifo_gray #','module async_fifo_gray_original #') | Set-Content -Encoding ascii async_fifo_gray_reference.sv
& "$bin\xvlog.bat" --sv user_reg_router.sv async_fifo_gray.sv async_fifo_gray_reference.sv tb_router.sv tb_fifo.sv
if($LASTEXITCODE){throw 'compile'}
foreach($top in @('tb_router','tb_fifo')) {
 $snapshot="${top}_snapshot"
 & "$bin\xelab.bat" -mt 2 -s $snapshot "work.$top"
 if($LASTEXITCODE){throw 'elab'}
 & "$bin\xsim.bat" $snapshot -runall -log "$top.log"
 if(Select-String -Quiet -Path "$top.log" -Pattern 'Failed to launch child process'){
  & "$bin\xsim.bat" $snapshot -runall -log "$top.log"
 }
 if($LASTEXITCODE){throw 'sim'}
 if(!(Select-String -Quiet -Path "$top.log" -Pattern $(if($top -eq 'tb_router'){'ROUTER_TEST_PASS'}else{'ALL_FIFO_CASES_PASS'}))){throw 'missing PASS'}
}
