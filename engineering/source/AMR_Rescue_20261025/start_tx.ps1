param([ValidateSet('S1','S2')][string]$Session='S2',[ValidateRange(1,10)][int]$Instances=10)
$ErrorActionPreference='Stop'
$runName='pc_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'_'+[Guid]::NewGuid().ToString('N').Substring(0,6)
$runDir=Join-Path (Join-Path $PSScriptRoot 'runs') $runName
New-Item -ItemType Directory -Path (Split-Path -Parent $runDir) -Force | Out-Null
Write-Host "Host truth/output directory: $runDir"
& python (Join-Path $PSScriptRoot 'pc_live_tx.py') --session $Session --instances $Instances --out $runDir
if ($LASTEXITCODE -ne 0) {throw 'TX service failed; inspect terminal output.'}
