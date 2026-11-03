$ErrorActionPreference='Stop'
$Root='F:\FPGA_Work\smartscan_bram_fix1_20261030'
Set-Location -LiteralPath $Root
$env:TEMP="$Root\build\tmp"
$env:TMP=$env:TEMP
& 'D:\Anaconda\python.exe' "$Root\build\pipeline_fix2.py" *> "$Root\build\supervisor_fix2.log"
$Code=$LASTEXITCODE
Set-Content -LiteralPath "$Root\build\supervisor_fix2.rc" -Value $Code
exit $Code
