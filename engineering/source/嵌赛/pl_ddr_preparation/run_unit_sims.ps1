$ErrorActionPreference = "Stop"
$vivadoBin = "D:\Xilinx2018.3\Vivado\2018.3\bin"
$rtl = @(
    "rtl/async_fifo_gray.sv",
    "rtl/user_ddr_iq_reader.sv",
    "rtl/iq_beat_unpacker.sv",
    "rtl/pl_ddr_iq_input_adapter.sv",
    "rtl/tensor_plane_beat_packer.sv",
    "rtl/user_ddr_tensor_writer.sv",
    "rtl/pl_ddr_tensor_output_adapter.sv"
)
$frozenCore = @(
    "../rf_cognitive_system/hardware/fpga/rtl/common/iq_stream_fifo.sv",
    "../rf_cognitive_system/hardware/fpga/rtl/framing/iq_frame_controller.sv",
    "../rf_cognitive_system/hardware/fpga/rtl/features/qam_feature_pipeline.sv",
    "../rf_cognitive_system/hardware/fpga/rtl/quantization/feature_quantizer.sv",
    "../rf_cognitive_system/hardware/fpga/rtl/tensor/tensor_packer.sv",
    "../rf_cognitive_system/hardware/fpga/rtl/common/mandatory_core_path.sv"
)

Push-Location $PSScriptRoot
try {
    python tools/byte_hex_codec.py encode generated/expected_tensor_plddr.bin generated/expected_tensor_plddr.hex
    if ($LASTEXITCODE -ne 0) { throw "Golden hex preparation failed" }

    & "$vivadoBin/xvlog.bat" --sv @rtl @frozenCore "tb/tb_pl_ddr_iq_input_adapter.sv" "tb/tb_pl_ddr_tensor_output_adapter.sv" "tb/tb_pl_ddr_mandatory_core_e2e.sv"
    if ($LASTEXITCODE -ne 0) { throw "xvlog failed" }

    & "$vivadoBin/xelab.bat" tb_pl_ddr_iq_input_adapter -s sim_iq_input
    if ($LASTEXITCODE -ne 0) { throw "input xelab failed" }
    & "$vivadoBin/xsim.bat" sim_iq_input -runall
    if ($LASTEXITCODE -ne 0) { throw "input xsim failed" }

    & "$vivadoBin/xelab.bat" tb_pl_ddr_tensor_output_adapter -s sim_tensor_output
    if ($LASTEXITCODE -ne 0) { throw "output xelab failed" }
    & "$vivadoBin/xsim.bat" sim_tensor_output -runall
    if ($LASTEXITCODE -ne 0) { throw "output xsim failed" }

    & "$vivadoBin/xelab.bat" tb_pl_ddr_mandatory_core_e2e -s sim_ddr_core_e2e
    if ($LASTEXITCODE -ne 0) { throw "E2E xelab failed" }
    & "$vivadoBin/xsim.bat" sim_ddr_core_e2e -runall
    if ($LASTEXITCODE -ne 0) { throw "E2E xsim failed" }

    python tools/byte_hex_codec.py decode generated/e2e_tensor_plddr.hex generated/e2e_tensor_plddr.bin
    if ($LASTEXITCODE -ne 0) { throw "E2E output decode failed" }
    python tools/plddr_tensor_to_csv.py generated/e2e_tensor_plddr.bin generated/e2e_tensor_capture.csv
    if ($LASTEXITCODE -ne 0) { throw "E2E CSV conversion failed" }
    python ../rf_cognitive_system/hardware/fpga/board_validation/compare_board_capture.py --tensor generated/e2e_tensor_capture.csv
    if ($LASTEXITCODE -ne 0) { throw "E2E Golden comparison failed" }
}
finally {
    Pop-Location
}
