$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$iv=Get-Command iverilog -ErrorAction SilentlyContinue; $vvp=Get-Command vvp -ErrorAction SilentlyContinue
if(-not $iv -or -not $vvp){Write-Host 'HDL_SIM result=SKIPPED reason=iverilog_not_installed'; exit 2}
$out=Join-Path $Root 'results/tb_smart_scan_boundary.vvp'
& $iv.Source -g2012 -s tb_smart_scan_boundary -o $out (Join-Path $Root 'rtl/window_mul_q15.sv') (Join-Path $Root 'rtl/fft_magnitude_square_u52.sv') (Join-Path $Root 'tb/tb_smart_scan_boundary.sv')
if($LASTEXITCODE){exit $LASTEXITCODE}; & $vvp.Source $out; if($LASTEXITCODE){exit $LASTEXITCODE}
Write-Host 'HDL_SIM result=PASS'
