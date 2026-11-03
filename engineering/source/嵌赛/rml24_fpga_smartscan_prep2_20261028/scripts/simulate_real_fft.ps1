# Real vendor XFFT behavioural simulation (no bitstream, no board).
#
# Compiles the full production datapath (Hann framer -> Xilinx XFFT 9.1
# behavioural sim netlist -> u54 magnitude-square -> fftshift double buffer)
# with xvlog/xelab/xsim inside an *independent ASCII temp working directory*.
# It never opens or modifies the frozen project
# vivado_fft/work_build/smartscan_fft_build.xpr or the migrated EDIF.
#
# The Vivado 2018.3 .bat launchers run their tool synchronously in the same
# cmd session (RDI_EXEC_DEFAULT is a plain `"%RDI_PROG%" %RDI_ARGS%`), so a
# PowerShell `&` call on the .bat is synchronous and returns the real exit
# code.  Each step is wrapped in a Start-Job so a per-step timeout is
# enforced even if the tool hangs.
#
#   SMARTSCAN_REAL_FFT_SIM result=PASS tones=2  (on success)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$vivadoBin = 'D:\Xilinx2018.3\Vivado\2018.3\bin'
$xvlog = Join-Path $vivadoBin 'xvlog.bat'
$xelab = Join-Path $vivadoBin 'xelab.bat'
$xsim  = Join-Path $vivadoBin 'xsim.bat'
$glblSrc  = 'D:\Xilinx2018.3\Vivado\2018.3\data\verilog\src\glbl.v'
$netlistSrc = Join-Path $root 'vivado_fft\sim_netlist\smartscan_fft_1024_sim_netlist.v'
$evidence = Join-Path $root 'evidence\real_fft_review_fix'
$work = Join-Path $env:TEMP 'rml24_smartscan_real_fft_sim'

function Invoke-VivadoTool {
    param(
        [Parameter(Mandatory = $true)][string]$Bat,
        [Parameter(Mandatory = $true)][string[]]$ToolArgs,
        [Parameter(Mandatory = $true)][string]$Log,
        [int]$TimeoutMs = 1500000
    )
    # Run the tool in a background job so we can enforce a timeout.  The .bat
    # launcher is synchronous by construction, so Wait-Job returning means the
    # real xvlog/xelab/xsim has already exited and $LASTEXITCODE is final.
    $job = Start-Job -ScriptBlock {
        param($bat, $toolArgs, $wd)
        Set-Location $wd
        $out = (& $bat @toolArgs 2>&1 | Out-String)
        [pscustomobject]@{ Out = $out; Rc = $LASTEXITCODE }
    } -ArgumentList $Bat, $ToolArgs, $work

    $timeoutSec = [int]($TimeoutMs / 1000)
    if (-not (Wait-Job $job -Timeout $timeoutSec)) {
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
        throw "REAL_FFT_SIM TIMEOUT after ${TimeoutMs}ms: $(Split-Path -Leaf $Bat)"
    }
    $res = Receive-Job $job
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    if ($null -eq $res) { $res = [pscustomobject]@{ Out = ''; Rc = 0 } }

    Set-Content -Path $Log -Value $res.Out -Encoding UTF8
    if ($res.Rc -ne 0) {
        throw "REAL_FFT_SIM step failed rc=$($res.Rc): $(Split-Path -Leaf $Bat); see $Log"
    }
    return $res.Out
}

# --- 1. independent ASCII work directory (all sources copied here) -------
if (Test-Path -LiteralPath $work) { Remove-Item -Recurse -Force -LiteralPath $work }
New-Item -ItemType Directory -Force -Path $work | Out-Null
New-Item -ItemType Directory -Force -Path $evidence | Out-Null

Copy-Item -LiteralPath $glblSrc    -Destination (Join-Path $work 'glbl.v') -Force
Copy-Item -LiteralPath $netlistSrc -Destination (Join-Path $work 'smartscan_fft_1024_sim_netlist.v') -Force
foreach ($f in @(
        'window_mul_q15.sv', 'fft_magnitude_square_u54.sv',
        'fft_psd_stream_writer.sv', 'smart_scan_framer.sv',
        'smart_scan_psd_buffers.sv', 'fft_vendor_ip_adapter.sv',
        'smart_scan_top.sv', 'hann_coeff_rom.v')) {
    Copy-Item -LiteralPath (Join-Path $root "rtl\$f") -Destination (Join-Path $work $f) -Force
}
Copy-Item -LiteralPath (Join-Path $root 'tb\tb_smart_scan_real_fft.sv') `
    -Destination (Join-Path $work 'tb_smart_scan_real_fft.sv') -Force
Copy-Item -Path (Join-Path $root 'vectors\real_fft\*.stim.hex') -Destination $work -Force

# --- 2. compile (plain Verilog first, then SystemVerilog) ----------------
Invoke-VivadoTool $xvlog @('glbl.v', 'smartscan_fft_1024_sim_netlist.v', 'hann_coeff_rom.v') `
    (Join-Path $evidence 'real_fft_xvlog_v.log') 1800000 | Out-Null
Invoke-VivadoTool $xvlog @('--sv',
        'window_mul_q15.sv', 'fft_magnitude_square_u54.sv',
        'fft_psd_stream_writer.sv', 'smart_scan_framer.sv',
        'smart_scan_psd_buffers.sv', 'fft_vendor_ip_adapter.sv',
        'smart_scan_top.sv', 'tb_smart_scan_real_fft.sv') `
    (Join-Path $evidence 'real_fft_xvlog_sv.log') 600000 | Out-Null

# --- 3. elaborate with unisim/secureip libraries + glbl ------------------
$snap = 'tb_smart_scan_real_fft_snap'
Invoke-VivadoTool $xelab @('--relax', '-L', 'unisims_ver', '-L', 'unimacro_ver',
    '-L', 'secureip', '-s', $snap, 'tb_smart_scan_real_fft', 'glbl') `
    (Join-Path $evidence 'real_fft_xelab.log') 1200000 | Out-Null

# --- 4. run with a per-step timeout --------------------------------------
$simlog = Join-Path $evidence 'real_fft_xsim.log'
$simOut = Invoke-VivadoTool $xsim @($snap, '-runall') $simlog 1200000
Copy-Item -Path (Join-Path $work 'psd_*.hex') -Destination $evidence -Force -ErrorAction SilentlyContinue

# --- 5. explicit PASS check ---------------------------------------------
if (-not ($simOut | Select-String -SimpleMatch 'TB_SMART_SCAN_REAL_FFT PASS tones=2')) {
    throw "REAL_FFT_SIM PASS token missing; see $simlog"
}
Write-Output 'SMARTSCAN_REAL_FFT_SIM result=PASS tones=2'
