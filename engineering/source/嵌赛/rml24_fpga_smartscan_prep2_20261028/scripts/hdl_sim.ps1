$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$VivadoBin='D:\Xilinx2018.3\Vivado\2018.3\bin'
$XVLog=Join-Path $VivadoBin 'xvlog.bat'
$XElab=Join-Path $VivadoBin 'xelab.bat'
$XSim=Join-Path $VivadoBin 'xsim.bat'
if(-not (Test-Path -LiteralPath $XVLog) -or
   -not (Test-Path -LiteralPath $XElab) -or
   -not (Test-Path -LiteralPath $XSim)) {
  Write-Host 'HDL_SIM result=SKIPPED reason=xsim_2018_3_not_found'
  exit 2
}
Push-Location $Root
try {
  # Compile the full production datapath (minus the vendor FFT netlist, which is
  # a black box for the real FFT and only exercised in the Procise OOC) plus all
  # self-contained testbenches.
  & $XVLog -sv `
    rtl/window_mul_q15.sv `
    rtl/fft_magnitude_square_u54.sv `
    rtl/fft_psd_stream_writer.sv `
    rtl/hann_coeff_rom.v `
    rtl/smart_scan_framer.sv `
    rtl/smart_scan_psd_buffers.sv `
    tb/tb_smart_scan_boundary.sv `
    tb/tb_fft_psd_stream_writer.sv `
    tb/tb_smart_scan_framer.sv `
    tb/tb_smart_scan_psd_buffers.sv
  if($LASTEXITCODE){exit $LASTEXITCODE}

  & $XElab tb_smart_scan_boundary -s smart_scan_boundary_prep2_auto
  if($LASTEXITCODE){exit $LASTEXITCODE}
  & $XSim smart_scan_boundary_prep2_auto -runall
  if($LASTEXITCODE){exit $LASTEXITCODE}

  & $XElab tb_fft_psd_stream_writer -s fft_psd_stream_writer_prep2_auto
  if($LASTEXITCODE){exit $LASTEXITCODE}
  & $XSim fft_psd_stream_writer_prep2_auto -runall
  if($LASTEXITCODE){exit $LASTEXITCODE}

  & $XElab tb_smart_scan_framer -s smart_scan_framer_prep2_auto
  if($LASTEXITCODE){exit $LASTEXITCODE}
  & $XSim smart_scan_framer_prep2_auto -runall
  if($LASTEXITCODE){exit $LASTEXITCODE}

  & $XElab tb_smart_scan_psd_buffers -s smart_scan_psd_buffers_prep2_auto
  if($LASTEXITCODE){exit $LASTEXITCODE}
  & $XSim smart_scan_psd_buffers_prep2_auto -runall
  if($LASTEXITCODE){exit $LASTEXITCODE}

  Write-Host 'HDL_SIM result=PASS tests=4 accepted_bins=2048 framer_words=4096 buffers_words=2048'
} finally {
  Pop-Location
}
