$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceTcl = Join-Path $ProjectRoot 'vivado_fft\build_xfft_1024.tcl'
$EvidenceDir = Join-Path $ProjectRoot 'vivado_fft\latest_result'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunDir = Join-Path $env:TEMP ("rml24_smartscan_xfft_" + $Stamp)
$Tcl = Join-Path $RunDir 'build_xfft_1024.tcl'
$Vivado = 'D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat'
$env:FMSH_PROCISE_PATH = 'D:\fudanwei\Procise'
if (-not (Test-Path -LiteralPath $Vivado -PathType Leaf)) {
    throw "Vivado 2018.3 not found: $Vivado"
}
New-Item -ItemType Directory -Path $RunDir | Out-Null
Copy-Item -LiteralPath $SourceTcl -Destination $Tcl
Push-Location $RunDir
try {
    & $Vivado -mode batch -notrace -source $Tcl 2>&1 |
        Tee-Object -FilePath 'build_xfft_console.log'
    if ($LASTEXITCODE -ne 0) { throw "Vivado returned $LASTEXITCODE" }
    if (-not (Select-String -LiteralPath 'build_xfft_console.log' `
            -SimpleMatch 'XFFT_BUILD_RESULT result=PASS' -Quiet)) {
        throw 'XFFT build PASS token missing'
    }
} finally {
    Pop-Location
}
New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
$EvidenceNames = @(
    'build_xfft_console.log', 'xfft_frozen_properties.txt',
    'xfft_vivado_utilization.rpt', 'xfft_vivado_timing_summary.rpt',
    'smartscan_fft_1024_synth.dcp'
)
foreach ($Name in $EvidenceNames) {
    $Source = Join-Path $RunDir $Name
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        Copy-Item -LiteralPath $Source -Destination $EvidenceDir -Force
    }
}
$Migrated = Join-Path $RunDir 'work_build\fmsh_file\procise_file'
if (-not (Test-Path -LiteralPath $Migrated -PathType Container)) {
    throw "migrated Procise files missing: $Migrated"
}
$MigratedEvidence = Join-Path $EvidenceDir 'migrated_procise'
if (Test-Path -LiteralPath $MigratedEvidence) {
    Remove-Item -LiteralPath $MigratedEvidence -Recurse -Force
}
Copy-Item -LiteralPath $Migrated -Destination $MigratedEvidence -Recurse
Set-Content -LiteralPath (Join-Path $EvidenceDir 'RUN_DIRECTORY.txt') `
           -Value $RunDir -Encoding ascii
Write-Output 'XFFT_BUILD_WRAPPER result=PASS production_bitstream=NO'
