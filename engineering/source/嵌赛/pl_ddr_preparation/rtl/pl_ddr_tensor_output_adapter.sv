`timescale 1ns/1ps
`default_nettype none

module pl_ddr_tensor_output_adapter #(
    parameter integer FRAME_LENGTH = 1024,
    parameter integer FRAME_COUNT = 19,
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer INDEX_WIDTH = 10,
    parameter integer FIFO_ADDR_WIDTH = 4,
    parameter integer EXPECTED_BEATS = FRAME_COUNT * (FRAME_LENGTH/64) * 5
) (
    input  wire                         core_clk,
    input  wire                         core_rst_n,
    input  wire                         core_start,
    input  wire [31:0]                  output_base_addr,
    input  wire                         core_write_valid,
    output wire                         core_write_ready,
    input  wire                         core_buffer_id,
    input  wire [FRAME_ID_WIDTH-1:0]    core_frame_id,
    input  wire [INDEX_WIDTH-1:0]       core_sample_index,
    input  wire [INDEX_WIDTH:0]         core_iq_i_addr,
    input  wire [INDEX_WIDTH:0]         core_iq_q_addr,
    input  wire [INDEX_WIDTH+1:0]       core_power_addr,
    input  wire [INDEX_WIDTH+1:0]       core_lag_re_addr,
    input  wire [INDEX_WIDTH+1:0]       core_lag_im_addr,
    input  wire signed [7:0]            core_iq_i_data,
    input  wire signed [7:0]            core_iq_q_data,
    input  wire signed [7:0]            core_power_data,
    input  wire signed [7:0]            core_lag_re_data,
    input  wire signed [7:0]            core_lag_im_data,
    input  wire                         core_frame_start,
    input  wire                         core_frame_done,
    input  wire                         core_frame_error,
    output wire [1:0]                   core_buffer_release,
    output wire                         core_active,
    output wire                         core_all_frames_enqueued,
    output wire                         core_protocol_error,
    output wire [31:0]                  core_accepted_samples,
    output wire [31:0]                  core_enqueued_beats,

    input  wire                         ddr_clk,
    input  wire                         ddr_rst_n,
    input  wire                         ddr_start,
    output wire                         ddr_busy,
    output wire                         ddr_done,
    output wire                         ddr_error,
    output wire [31:0]                  ddr_accepted_beats,
    output wire [31:0]                  User_Ddr_awwaddr,
    output wire [511:0]                 User_Ddr_awwdata,
    output wire [71:0]                  User_Ddr_awwinfo,
    output wire                         User_Ddr_awwvalid,
    input  wire                         User_Ddr_awwready
);
    wire [543:0] packer_command;
    wire packer_valid;
    wire packer_ready;
    wire [543:0] fifo_command;
    wire fifo_valid;
    wire fifo_ready;

    tensor_plane_beat_packer #(
        .FRAME_LENGTH(FRAME_LENGTH), .FRAME_COUNT(FRAME_COUNT),
        .FRAME_ID_WIDTH(FRAME_ID_WIDTH), .INDEX_WIDTH(INDEX_WIDTH)
    ) packer (
        .clk(core_clk), .rst_n(core_rst_n), .start(core_start),
        .output_base_addr(output_base_addr),
        .s_write_valid(core_write_valid), .s_write_ready(core_write_ready),
        .s_buffer_id(core_buffer_id), .s_frame_id(core_frame_id),
        .s_sample_index(core_sample_index), .s_iq_i_addr(core_iq_i_addr),
        .s_iq_q_addr(core_iq_q_addr), .s_power_addr(core_power_addr),
        .s_lag_re_addr(core_lag_re_addr), .s_lag_im_addr(core_lag_im_addr),
        .s_iq_i_data(core_iq_i_data), .s_iq_q_data(core_iq_q_data),
        .s_power_data(core_power_data), .s_lag_re_data(core_lag_re_data),
        .s_lag_im_data(core_lag_im_data), .s_frame_start(core_frame_start),
        .s_frame_done(core_frame_done), .s_frame_error(core_frame_error),
        .buffer_release(core_buffer_release), .beat_command(packer_command),
        .beat_valid(packer_valid), .beat_ready(packer_ready),
        .active(core_active), .all_frames_enqueued(core_all_frames_enqueued),
        .protocol_error(core_protocol_error),
        .accepted_samples(core_accepted_samples), .enqueued_beats(core_enqueued_beats)
    );

    async_fifo_gray #(.DATA_WIDTH(544), .ADDR_WIDTH(FIFO_ADDR_WIDTH)) cdc_fifo (
        .s_clk(core_clk), .s_rst_n(core_rst_n), .s_data(packer_command),
        .s_valid(packer_valid), .s_ready(packer_ready),
        .m_clk(ddr_clk), .m_rst_n(ddr_rst_n), .m_data(fifo_command),
        .m_valid(fifo_valid), .m_ready(fifo_ready)
    );

    user_ddr_tensor_writer #(.EXPECTED_BEATS(EXPECTED_BEATS)) writer (
        .clk(ddr_clk), .rst_n(ddr_rst_n), .start(ddr_start),
        .beat_command(fifo_command), .beat_valid(fifo_valid),
        .beat_ready(fifo_ready), .busy(ddr_busy), .done(ddr_done),
        .error(ddr_error), .accepted_beats(ddr_accepted_beats),
        .User_Ddr_awwaddr(User_Ddr_awwaddr),
        .User_Ddr_awwdata(User_Ddr_awwdata),
        .User_Ddr_awwinfo(User_Ddr_awwinfo),
        .User_Ddr_awwvalid(User_Ddr_awwvalid),
        .User_Ddr_awwready(User_Ddr_awwready)
    );
endmodule

`default_nettype wire
