param(
    [string]$PythonExe = 'D:\radioconda\python.exe',
    [string]$Bind = '192.168.126.50',
    [string]$TxUri = ''
)
$ErrorActionPreference = 'Stop'
$runName = 'clean_v2_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [Guid]::NewGuid().ToString('N').Substring(0,6)
$runDir = Join-Path (Join-Path $PSScriptRoot 'runs') $runName
$argsList = @('-I', (Join-Path $PSScriptRoot 'pc_clean_v2_tx.py'), '--out', $runDir, '--bind', $Bind)
if ($TxUri) { $argsList += @('--tx-uri', $TxUri) }
Write-Host "Private truth/output directory: $runDir"
& $PythonExe @argsList
if ($LASTEXITCODE -ne 0) { throw 'Clean-v2 TX failed; inspect terminal output.' }
