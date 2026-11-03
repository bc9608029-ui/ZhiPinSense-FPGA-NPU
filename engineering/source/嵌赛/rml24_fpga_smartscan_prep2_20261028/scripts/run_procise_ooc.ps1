param(
    [string]$ProciseRoot = 'D:\fudanwei\Procise'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Target = Join-Path $ProjectRoot 'procise_target'
$Exe = Join-Path $ProciseRoot 'bin\procise.exe'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunDir = Join-Path $env:TEMP ("rml24_smartscan_procise_ooc_" + $Stamp)

if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
    throw "Procise executable not found: $Exe"
}

# Procise 2025.1.1 cannot reliably parse a source path containing Chinese
# characters and accepts Verilog content but not the .sv suffix in this flow.
# Stage byte-identical sources in a fresh ASCII-only temporary directory.
New-Item -ItemType Directory -Path $RunDir | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'rtl\window_mul_q15.sv') `
          -Destination (Join-Path $RunDir 'window_mul_q15.v')
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'rtl\fft_psd_stream_writer.sv') `
          -Destination (Join-Path $RunDir 'fft_psd_stream_writer.v')
Copy-Item -LiteralPath (Join-Path $Target 'smart_scan_postfft_ooc_harness.v') `
          -Destination (Join-Path $RunDir 'smart_scan_postfft_ooc_harness.v')
Copy-Item -LiteralPath (Join-Path $Target 'run_postfft_ooc.tcl') `
          -Destination (Join-Path $RunDir 'run_postfft_ooc.tcl')

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
        -ArgumentList (Join-Path $RunDir 'run_postfft_ooc.tcl') `
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
            -SimpleMatch 'SMARTSCAN_PROCISE_OOC_RESULT result=PASS' -Quiet)) {
        throw 'Procise log lacks the fail-closed PASS token'
    }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Path (Join-Path $Target 'latest_result') -Force | Out-Null
$EvidenceNames = @(
    'procise_console.log', 'procise_stderr.log', 'smart_scan_postfft_ooc.fpe',
    'smart_scan_postfft_ooc.edf', 'smart_scan_postfft_ooc.phy'
)
foreach ($Name in $EvidenceNames) {
    $Source = Join-Path $RunDir $Name
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        Copy-Item -LiteralPath $Source -Destination (Join-Path $Target 'latest_result') -Force
    }
}
Set-Content -LiteralPath (Join-Path $Target 'latest_result\RUN_DIRECTORY.txt') `
           -Value $RunDir -Encoding ascii
Write-Output 'PROCISE_OOC_WRAPPER result=PASS production_bitstream=NO'
