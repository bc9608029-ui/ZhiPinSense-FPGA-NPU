$ErrorActionPreference = 'Stop'

$vivadoBin = 'D:\Xilinx2018.3\Vivado\2018.3\bin'
$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$fpgaRoot = Join-Path $workspace 'rf_cognitive_system\hardware\fpga'
$snapshot = 'board_top_50mhz_resetfix_sim'

$sources = @(
    "$fpgaRoot\rtl\common\iq_stream_fifo.sv",
    "$fpgaRoot\rtl\framing\iq_frame_controller.sv",
    "$fpgaRoot\rtl\features\qam_feature_pipeline.sv",
    "$fpgaRoot\rtl\quantization\feature_quantizer.sv",
    "$fpgaRoot\rtl\tensor\tensor_packer.sv",
    "$fpgaRoot\rtl\common\mandatory_core_path.sv",
    "$fpgaRoot\rtl\board\fixed_iq_rom.sv",
    "$fpgaRoot\rtl\board\iq_replay_controller.sv",
    "$fpgaRoot\rtl\board\board_mandatory_core_test_top.sv",
    "$fpgaRoot\tb\integration\tb_board_mandatory_core_test_top.sv"
)

Push-Location $fpgaRoot
try {
    & "$vivadoBin\xvlog.bat" -sv @sources
    if ($LASTEXITCODE -ne 0) { throw "xvlog failed with exit code $LASTEXITCODE" }

    & "$vivadoBin\xelab.bat" tb_board_mandatory_core_test_top -s $snapshot -debug typical
    if ($LASTEXITCODE -ne 0) { throw "xelab failed with exit code $LASTEXITCODE" }

    & "$vivadoBin\xsim.bat" $snapshot -runall
    if ($LASTEXITCODE -ne 0) { throw "xsim failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
