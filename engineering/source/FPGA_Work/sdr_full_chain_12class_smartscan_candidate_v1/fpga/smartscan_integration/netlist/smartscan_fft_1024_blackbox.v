`timescale 1ps/1ps
// Black-box stub for the Xilinx XFFT 9.1 netlist
// `smartscan_fft_1024_z030.edif` (board part xc7z030ffg676-2, standard Unisim
// primitives).  Empty module + `synthesis syn_black_box` directive, exactly the
// board's own `AI_Mate_stub.v` pattern: synthesis infers a black box and the
// implementation is linked from the EDIF at implementation time.
//
// IMPORTANT: do NOT use the Verilog `(* black_box *)` attribute here.  In this
// project Vivado's `update_compile_order` reacts to that attribute by
// auto-disabling the sibling EDIF (`AutoDisabled=1`), which then leaves the FFT
// cell unresolved at opt_design (DRC INBB-3).  The empty-body + syn_black_box
// comment directive keeps the EDIF enabled, matching the frozen AI_Mate flow.
//
// Port list is the generated .veo/.vho instantiation template.
module smartscan_fft_1024 (
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
/* synthesis syn_black_box black_box_pad_pin="aclk,aresetn,s_axis_config_tdata[7:0],s_axis_config_tvalid,s_axis_config_tready,s_axis_data_tdata[31:0],s_axis_data_tvalid,s_axis_data_tready,s_axis_data_tlast,m_axis_data_tdata[63:0],m_axis_data_tuser[15:0],m_axis_data_tvalid,m_axis_data_tlast,event_frame_started,event_tlast_unexpected,event_tlast_missing,event_data_in_channel_halt" */;
endmodule
