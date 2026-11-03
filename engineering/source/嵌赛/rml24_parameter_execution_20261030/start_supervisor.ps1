$ErrorActionPreference='Stop'
$Root='F:\嵌赛\rml24_parameter_execution_20261030'
Set-Location -LiteralPath $Root
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'D:\Anaconda\python.exe' -I "$Root\supervise.py" *> "$Root\supervisor.log"
$code=$LASTEXITCODE
Set-Content -LiteralPath "$Root\supervisor.rc" -Value $code
exit $code
