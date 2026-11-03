$ErrorActionPreference='Stop'
$Root='F:\FPGA_Work\smartscan_bram_fix1_20261030'
Set-Location -LiteralPath $Root
$env:TEMP="$Root\build\tmp"
$env:TMP=$env:TEMP
& 'D:\Anaconda\python.exe' "$Root\build\bitgen_pipeline.py" *> "$Root\build\bitgen_supervisor.log"
$code=$LASTEXITCODE
Set-Content -LiteralPath "$Root\build\bitgen_supervisor.rc" -Value $code
exit $code
