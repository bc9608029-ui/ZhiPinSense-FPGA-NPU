param(
    [string]$ProciseRoot = 'D:\fudanwei\Procise'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Target = Join-Path $ProjectRoot 'procise_target'
$Exe = Join-Path $ProciseRoot 'bin\procise.exe'
$MigratedEdif = Join-Path $ProjectRoot 'vivado_fft\latest_result\migrated_procise\smartscan_fft_1024.edif'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunDir = Join-Path $env:TEMP ("rml24_smartscan_combined_ooc_" + $Stamp)

if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    throw "Procise executable not found: $Exe"
}
if (-not (Test-Path -LiteralPath $MigratedEdif -PathType Leaf)) {
    throw "migrated XFFT EDIF missing; run scripts/build_vivado_xfft.ps1 first: $MigratedEdif"
}

# Procise 2025.1.1 cannot reliably parse a source path containing Chinese
# characters and accepts Verilog content but not the .sv suffix in this flow.
# Stage byte-identical sources and the migrated netlist in a fresh ASCII-only
# temporary directory.
New-Item -ItemType Directory -Path $RunDir | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'rtl\window_mul_q15.sv') `
          -Destination (Join-Path $RunDir 'window_mul_q15.v')
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'rtl\fft_psd_stream_writer.sv') `
          -Destination (Join-Path $RunDir 'fft_psd_stream_writer.v')
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'rtl\fft_vendor_ip_adapter.sv') `
          -Destination (Join-Path $RunDir 'fft_vendor_ip_adapter.v')
Copy-Item -LiteralPath (Join-Path $Target 'smart_scan_combined_ooc_harness.v') `
          -Destination (Join-Path $RunDir 'smart_scan_combined_ooc_harness.v')
Copy-Item -LiteralPath (Join-Path $Target 'run_combined_ooc.tcl') `
          -Destination (Join-Path $RunDir 'run_combined_ooc.tcl')
Copy-Item -LiteralPath (Join-Path $Target 'smartscan_fft_1024_blackbox.v') `
          -Destination (Join-Path $RunDir 'smartscan_fft_1024_blackbox.v')
Copy-Item -LiteralPath $MigratedEdif `
          -Destination (Join-Path $RunDir 'smartscan_fft_1024.edif')

$env:TCL_LIBRARY = Join-Path $ProciseRoot 'tcl8.4'
$env:ICTIME_HOME = $ProciseRoot
$env:APP_DIR = $ProciseRoot
$env:FMSH_DB = Join-Path $ProciseRoot 'db'
$env:PATH = (Join-Path $ProciseRoot 'dll') + ';' +
            (Join-Path $ProciseRoot 'bin') + ';' + $env:PATH

Push-Location $RunDir
try {
    $Stdout = Join-Path $RunDir 'procise_console.log'
    $Stderr = Join-Path $RunDir 'procise_stderr.log'
    $Process = Start-Process -FilePath $Exe `
        -ArgumentList (Join-Path $RunDir 'run_combined_ooc.tcl') `
        -WorkingDirectory $RunDir -NoNewWindow -PassThru -Wait `
        -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    Get-Content -LiteralPath $Stdout
    if ((Test-Path -LiteralPath $Stderr) -and
        ((Get-Item -LiteralPath $Stderr).Length -gt 0)) {
        Get-Content -LiteralPath $Stderr | Write-Warning
    }
    if ($Process.ExitCode -ne 0) {
        throw "Procise returned exit code $($Process.ExitCode)"
    }
    if (-not (Select-String -LiteralPath (Join-Path $RunDir 'procise_console.log') `
            -SimpleMatch 'SMARTSCAN_COMBINED_OOC_RESULT result=PASS' -Quiet)) {
        throw 'Procise log lacks the fail-closed PASS token'
    }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Path (Join-Path $Target 'latest_combined_result') -Force | Out-Null
$EvidenceNames = @(
    'procise_console.log', 'procise_stderr.log', 'smart_scan_combined_ooc.fpe',
    'smart_scan_combined_ooc.edf', 'smart_scan_combined_ooc.phy'
)
foreach ($Name in $EvidenceNames) {
    $Source = Join-Path $RunDir $Name
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        Copy-Item -LiteralPath $Source `
                   -Destination (Join-Path $Target 'latest_combined_result') -Force
    }
}
Set-Content -LiteralPath (Join-Path $Target 'latest_combined_result\RUN_DIRECTORY.txt') `
           -Value $RunDir -Encoding ascii
Write-Output 'COMBINED_OOC_WRAPPER result=PASS production_bitstream=NO'
