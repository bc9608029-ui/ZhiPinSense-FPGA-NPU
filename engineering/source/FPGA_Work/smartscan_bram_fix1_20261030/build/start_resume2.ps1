$ErrorActionPreference='Stop'
$Root='F:\FPGA_Work\smartscan_bram_fix1_20261030'
Set-Location -LiteralPath $Root
$env:TEMP="$Root\build\tmp"
$env:TMP=$env:TEMP
& 'D:\Anaconda\python.exe' "$Root\build\pipeline_resume2.py" *> "$Root\build\supervisor_resume2.log"
$Code=$LASTEXITCODE
Set-Content -LiteralPath "$Root\build\supervisor_resume2.rc" -Value $Code
exit $Code
