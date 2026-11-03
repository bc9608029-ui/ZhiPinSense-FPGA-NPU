$ErrorActionPreference = "Stop"
$vivadoBin = "D:\Xilinx2018.3\Vivado\2018.3\bin"
$adapterRtl = @(
    "deps/adapters/async_fifo_gray.sv",
    "deps/adapters/user_ddr_iq_reader.sv",
    "deps/adapters/iq_beat_unpacker.sv",
    "deps/adapters/pl_ddr_iq_input_adapter.sv",
    "deps/adapters/tensor_plane_beat_packer.sv",
    "deps/adapters/user_ddr_tensor_writer.sv",
    "deps/adapters/pl_ddr_tensor_output_adapter.sv"
)
$integrationRtl = @(
    "rtl/job_domain_controller.sv",
    "rtl/pl_ddr_mandatory_core_regs.sv",
    "rtl/pl_ddr_mandatory_core_engine.sv"
)
$frozenCore = @(
    "deps/frozen/iq_stream_fifo.sv",
    "deps/frozen/iq_frame_controller.sv",
    "deps/frozen/qam_feature_pipeline.sv",
    "deps/frozen/feature_quantizer.sv",
    "deps/frozen/tensor_packer.sv",
    "deps/frozen/mandatory_core_path.sv"
)

Push-Location $PSScriptRoot
try {
    & "$vivadoBin/xvlog.bat" --sv @adapterRtl @integrationRtl @frozenCore "tb/tb_pl_ddr_mandatory_core_engine.sv"
    if ($LASTEXITCODE -ne 0) { throw "xvlog failed" }
    & "$vivadoBin/xelab.bat" tb_pl_ddr_mandatory_core_engine -s sim_pl_ddr_engine
    if ($LASTEXITCODE -ne 0) { throw "xelab failed" }
    & "$vivadoBin/xsim.bat" sim_pl_ddr_engine -runall
    if ($LASTEXITCODE -ne 0) { throw "xsim failed" }
}
finally {
    Pop-Location
}
