# Smart-scan PS/PL engine bus simulation + fault injection (no bitstream, no board).
#
# Compiles smart_scan_pspl_engine (register bank + DDR IQ adapter + frame marker
# + smart_scan_top + the real Xilinx XFFT 9.1 behavioural sim netlist) with
# xvlog/xelab/xsim inside an independent ASCII temp directory. It never opens or
# modifies the frozen project or the migrated EDIF.
#
#   TB_SMART_SCAN_PSPL PASS cases=3 faults=2  (on success)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$vivadoBin = 'D:\Xilinx2018.3\Vivado\2018.3\bin'
$xvlog = Join-Path $vivadoBin 'xvlog.bat'
$xelab = Join-Path $vivadoBin 'xelab.bat'
$xsim  = Join-Path $vivadoBin 'xsim.bat'
$glblSrc  = 'D:\Xilinx2018.3\Vivado\2018.3\data\verilog\src\glbl.v'
$netlistSrc = Join-Path $root 'vivado_fft\sim_netlist\smartscan_fft_1024_sim_netlist.v'
$evidence = Join-Path $root 'evidence\pspl_sim'
$work = Join-Path $env:TEMP 'rml24_smartscan_pspl_sim'

function Invoke-VivadoTool {
    param(
        [Parameter(Mandatory = $true)][string]$Bat,
        [Parameter(Mandatory = $true)][string[]]$ToolArgs,
        [Parameter(Mandatory = $true)][string]$Log,
        [int]$TimeoutMs = 1500000
    )
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
        throw "PSPL_SIM TIMEOUT after ${TimeoutMs}ms: $(Split-Path -Leaf $Bat)"
    }
    $res = Receive-Job $job
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    if ($null -eq $res) { $res = [pscustomobject]@{ Out = ''; Rc = 0 } }

    Set-Content -Path $Log -Value $res.Out -Encoding UTF8
    if ($res.Rc -ne 0) {
        throw "PSPL_SIM step failed rc=$($res.Rc): $(Split-Path -Leaf $Bat); see $Log"
    }
    return $res.Out
}

# --- 1. independent ASCII work directory -----------------------------------
if (Test-Path -LiteralPath $work) { Remove-Item -Recurse -Force -LiteralPath $work }
New-Item -ItemType Directory -Force -Path $work | Out-Null
New-Item -ItemType Directory -Force -Path $evidence | Out-Null

Copy-Item -LiteralPath $glblSrc    -Destination (Join-Path $work 'glbl.v') -Force
Copy-Item -LiteralPath $netlistSrc -Destination (Join-Path $work 'smartscan_fft_1024_sim_netlist.v') -Force
foreach ($f in @(
        'window_mul_q15.sv', 'fft_magnitude_square_u54.sv',
        'fft_psd_stream_writer.sv', 'smart_scan_framer.sv',
        'smart_scan_psd_buffers.sv', 'fft_vendor_ip_adapter.sv',
        'smart_scan_top.sv', 'hann_coeff_rom.v',
        'smart_scan_iq_frame_marker.sv', 'smart_scan_pspl_regs.sv',
        'smart_scan_pspl_engine.sv')) {
    Copy-Item -LiteralPath (Join-Path $root "rtl\$f") -Destination (Join-Path $work $f) -Force
}
foreach ($f in @('async_fifo_gray.sv', 'iq_beat_unpacker.sv',
                 'pl_ddr_iq_input_adapter.sv', 'user_ddr_iq_reader.sv')) {
    Copy-Item -LiteralPath (Join-Path $root "deps\adapters\$f") -Destination (Join-Path $work $f) -Force
}
Copy-Item -LiteralPath (Join-Path $root 'deps\rtl\job_domain_controller.sv') `
    -Destination (Join-Path $work 'job_domain_controller.sv') -Force
Copy-Item -LiteralPath (Join-Path $root 'tb\tb_smart_scan_pspl.sv') `
    -Destination (Join-Path $work 'tb_smart_scan_pspl.sv') -Force

# --- 2. compile (plain Verilog first, then SystemVerilog) -------------------
Invoke-VivadoTool $xvlog @('glbl.v', 'smartscan_fft_1024_sim_netlist.v', 'hann_coeff_rom.v') `
    (Join-Path $evidence 'pspl_xvlog_v.log') 1800000 | Out-Null
Invoke-VivadoTool $xvlog @('--sv',
        'window_mul_q15.sv', 'fft_magnitude_square_u54.sv',
        'fft_psd_stream_writer.sv', 'smart_scan_framer.sv',
        'smart_scan_psd_buffers.sv', 'fft_vendor_ip_adapter.sv',
        'smart_scan_top.sv', 'smart_scan_iq_frame_marker.sv',
        'smart_scan_pspl_regs.sv', 'smart_scan_pspl_engine.sv',
        'async_fifo_gray.sv', 'iq_beat_unpacker.sv',
        'pl_ddr_iq_input_adapter.sv', 'user_ddr_iq_reader.sv',
        'job_domain_controller.sv', 'tb_smart_scan_pspl.sv') `
    (Join-Path $evidence 'pspl_xvlog_sv.log') 600000 | Out-Null

# --- 3. elaborate with unisim/secureip libraries + glbl ---------------------
$snap = 'tb_smart_scan_pspl_snap'
Invoke-VivadoTool $xelab @('--relax', '-L', 'unisims_ver', '-L', 'unimacro_ver',
    '-L', 'secureip', '-s', $snap, 'tb_smart_scan_pspl', 'glbl') `
    (Join-Path $evidence 'pspl_xelab.log') 1200000 | Out-Null

# --- 4. run with a per-step timeout -----------------------------------------
$simlog = Join-Path $evidence 'pspl_xsim.log'
$simOut = Invoke-VivadoTool $xsim @($snap, '-runall') $simlog 1200000

# --- 5. explicit PASS check -------------------------------------------------
if (-not ($simOut | Select-String -SimpleMatch 'TB_SMART_SCAN_PSPL PASS cases=3 faults=2')) {
    throw "PSPL_SIM PASS token missing; see $simlog"
}
Write-Output 'SMARTSCAN_PSPL_SIM result=PASS cases=3 faults=2'
