param([string]$Simulator = "auto")
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
$Vvp = Get-Command vvp -ErrorAction SilentlyContinue
if ($Simulator -eq 'auto' -and $Iverilog -and $Vvp) { $Simulator = 'iverilog' }
if ($Simulator -ne 'iverilog') {
    Write-Host 'HDL_SIM_RESULT result=SKIPPED reason=no_supported_simulator'
    exit 2
}
$Out = Join-Path $env:TEMP 'tb_frame_statistics.vvp'
& $Iverilog.Source -g2012 -s tb_frame_statistics -o $Out `
    (Join-Path $Root 'rtl/frame_statistics.sv') `
    (Join-Path $Root 'tb/tb_frame_statistics.sv')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Vvp.Source $Out
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'HDL_SIM_RESULT result=PASS simulator=iverilog'
