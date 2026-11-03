$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Tcl = Join-Path $ProjectRoot 'vivado_fft\query_xfft_config.tcl'
$Vivado = 'D:\Xilinx2018.3\Vivado\2018.3\bin\vivado.bat'
if (-not (Test-Path -LiteralPath $Vivado -PathType Leaf)) {
    throw "Vivado 2018.3 not found: $Vivado"
}
Push-Location (Split-Path -Parent $Tcl)
try {
    & $Vivado -mode batch -notrace -source $Tcl 2>&1 |
        Tee-Object -FilePath 'query_xfft_console.log'
    if ($LASTEXITCODE -ne 0) { throw "Vivado returned $LASTEXITCODE" }
    if (-not (Select-String -LiteralPath 'query_xfft_console.log' `
            -SimpleMatch 'XFFT_QUERY_RESULT result=PASS' -Quiet)) {
        throw 'XFFT query PASS token missing'
    }
} finally {
    Pop-Location
}
Write-Output 'XFFT_QUERY_WRAPPER result=PASS'
