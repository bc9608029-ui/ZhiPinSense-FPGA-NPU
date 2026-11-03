$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$vivado = 'D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat'
$migration = 'D:\FMSH\JFM_Kits\ip_patch\fmsh_migration_process\fmsh_migration_process.tcl'
$procise = 'D:\fudanwei\Procise'
$runFile = Join-Path $root 'vivado_fft\latest_result\RUN_DIRECTORY.txt'

foreach ($p in @($vivado, $migration, $procise, $runFile)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "required path missing: $p" }
}
$runDir = (Get-Content -LiteralPath $runFile -Raw).Trim()
$project = Join-Path $runDir 'work_build\smartscan_fft_build.xpr'
if (-not (Test-Path -LiteralPath $project)) { throw "Vivado project missing: $project" }

$env:FMSH_PROCISE_PATH = $procise
$tcl = Join-Path $root 'vivado_fft\migrate_xfft_manual_to_procise.tcl'
$frozenDcp = Join-Path $root 'vivado_fft\latest_result\smartscan_fft_1024_synth.dcp'
$outDir = Join-Path $root 'vivado_fft\migration_result'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stdout = Join-Path $outDir 'migration_console.log'
$stderr = Join-Path $outDir 'migration_stderr.log'
$p = Start-Process -FilePath $vivado -ArgumentList @(
    '-mode','batch','-nojournal','-nolog','-source',$tcl,
    '-tclargs',$project,$migration,$frozenDcp
) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
if ($p.ExitCode -ne 0) { throw "Vivado migration failed rc=$($p.ExitCode); see $stdout" }
if (-not (Select-String -LiteralPath $stdout -SimpleMatch 'XFFT_MIGRATION_RESULT result=PASS' -Quiet)) {
    throw "migration PASS token missing: $stdout"
}
$generated = Join-Path $runDir 'work_build\fmsh_file\procise_file'
if (-not (Test-Path -LiteralPath $generated)) { throw "migration output missing: $generated" }
Copy-Item -LiteralPath $generated -Destination (Join-Path $outDir 'procise_file') -Recurse -Force
Set-Content -LiteralPath (Join-Path $outDir 'SOURCE_PROJECT.txt') -Value $project -Encoding ascii
Write-Output "XFFT_MIGRATION_WRAPPER result=PASS output=$outDir production_bitstream=NO"
