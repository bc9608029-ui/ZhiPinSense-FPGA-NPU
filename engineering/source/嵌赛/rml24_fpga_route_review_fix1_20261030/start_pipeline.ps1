$ErrorActionPreference='Stop'
$Root='F:\FPGA_Work\smartscan_bram_fix1_20261030'
Set-Location -LiteralPath $Root
$env:TEMP="$Root\build\tmp"
$env:TMP=$env:TEMP
& 'D:\Anaconda\python.exe' "$Root\build\pipeline_fix1.py" *> "$Root\build\supervisor.log"
$Code=$LASTEXITCODE
Set-Content -LiteralPath "$Root\build\supervisor.rc" -Value $Code
exit $Code
