`timescale 1ns/1ps
`default_nettype none

module pl_ddr_iq_input_adapter #(
    parameter integer FIFO_ADDR_WIDTH = 4
) (
    input  wire         ddr_clk,
    input  wire         ddr_rst_n,
    input  wire         ddr_start,
    input  wire [31:0]  iq_base_addr,
    input  wire [31:0]  iq_byte_count,
    output wire         ddr_busy,
    output wire         ddr_done,
    output wire         ddr_error,

    output wire [31:0]  User_Ddr_araddr,
    output wire         User_Ddr_arvalid,
    output wire [31:0]  User_Ddr_arinfo,
    input  wire         User_Ddr_arready,
    input  wire [511:0] User_Ddr_rdata,
    input  wire         User_Ddr_rvalid,
    input  wire [31:0]  User_Ddr_rinfo,
    output wire         User_Ddr_rready,

    input  wire         core_clk,
    input  wire         core_rst_n,
    output wire signed [15:0] core_i,
    output wire signed [15:0] core_q,
    output wire         core_valid,
    input  wire         core_ready,
    output wire [31:0]  core_accepted_samples
);
    wire [511:0] reader_data;
    wire reader_valid;
    wire reader_ready;
    wire [511:0] fifo_data;
    wire fifo_valid;
    wire fifo_ready;

    user_ddr_iq_reader reader (
        .clk(ddr_clk), .rst_n(ddr_rst_n), .start(ddr_start),
        .base_addr(iq_base_addr), .byte_count(iq_byte_count),
        .busy(ddr_busy), .done(ddr_done), .error(ddr_error),
        .User_Ddr_araddr(User_Ddr_araddr), .User_Ddr_arvalid(User_Ddr_arvalid),
        .User_Ddr_arinfo(User_Ddr_arinfo), .User_Ddr_arready(User_Ddr_arready),
        .User_Ddr_rdata(User_Ddr_rdata), .User_Ddr_rvalid(User_Ddr_rvalid),
        .User_Ddr_rinfo(User_Ddr_rinfo), .User_Ddr_rready(User_Ddr_rready),
        .beat_data(reader_data), .beat_valid(reader_valid), .beat_ready(reader_ready)
    );

    async_fifo_gray #(.DATA_WIDTH(512), .ADDR_WIDTH(FIFO_ADDR_WIDTH)) cdc_fifo (
        .s_clk(ddr_clk), .s_rst_n(ddr_rst_n), .s_data(reader_data),
        .s_valid(reader_valid), .s_ready(reader_ready),
        .m_clk(core_clk), .m_rst_n(core_rst_n), .m_data(fifo_data),
        .m_valid(fifo_valid), .m_ready(fifo_ready)
    );

    iq_beat_unpacker unpacker (
        .clk(core_clk), .rst_n(core_rst_n), .beat_data(fifo_data),
        .beat_valid(fifo_valid), .beat_ready(fifo_ready),
        .iq_i(core_i), .iq_q(core_q), .iq_valid(core_valid),
        .iq_ready(core_ready), .accepted_samples(core_accepted_samples)
    );
endmodule

`default_nettype wire
