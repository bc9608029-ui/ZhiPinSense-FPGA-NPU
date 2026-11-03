`timescale 1ps/1ps
// Black-box declaration for the migrated Xilinx XFFT 9.1 netlist
// (vivado_fft/latest_result/migrated_procise/smartscan_fft_1024.edif). Provides
// the Verilog interface so Procise's elaborator can resolve instantiations of
// `smartscan_fft_1024`; the gate-level implementation comes from the EDIF
// netlist, never from this empty body. Port list is byte-for-byte the generated
// .veo/.vho instantiation template.
(* black_box *)module smartscan_fft_1024 (
    input  wire        aclk,
    input  wire        aresetn,
    input  wire [7:0]  s_axis_config_tdata,
    input  wire        s_axis_config_tvalid,
    output wire        s_axis_config_tready,
    input  wire [31:0] s_axis_data_tdata,
    input  wire        s_axis_data_tvalid,
    output wire        s_axis_data_tready,
    input  wire        s_axis_data_tlast,
    output wire [63:0] m_axis_data_tdata,
    output wire [15:0] m_axis_data_tuser,
    output wire        m_axis_data_tvalid,
    output wire        m_axis_data_tlast,
    output wire        event_frame_started,
    output wire        event_tlast_unexpected,
    output wire        event_tlast_missing,
    output wire        event_data_in_channel_halt
);
endmodule
