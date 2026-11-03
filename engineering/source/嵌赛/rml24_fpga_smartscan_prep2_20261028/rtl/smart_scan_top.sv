`timescale 1ns/1ps
// Production smart-scan datapath top: PS->PL int16 I/Q stream -> Hann window ->
// migrated XFFT 9.1 (1024-pt, 27-bit out) -> u54 magnitude-square + fftshift +
// ping-pong -> double-buffer PSD readback + status.
//
// This is the real datapath (not the OOC smoke harness). The AXI-Lite/DMA glue
// to the PS is a separate integration wrapper; this module exposes a clean
// streaming input and a synchronous PSD readback so it can be OOC-verified and
// later wrapped by the board-specific PS interface.
module smart_scan_top (
    input  wire         clk,
    input  wire         rst_n,
    // PS->PL IQ input stream ({Q[15:0], I[15:0]} per beat, int16 I/Q).
    input  wire [31:0]  s_axis_iq_tdata,
    input  wire         s_axis_iq_tvalid,
    output wire         s_axis_iq_tready,
    input  wire         s_axis_iq_tlast,
    // PSD readback (PS reads the committed bank).
    input  wire         rd_bank,
    input  wire [9:0]   rd_addr,
    output wire [63:0]  rd_data,
    // status
    output wire [7:0]   version,
    output wire [31:0]  status_frame_id,
    output wire         status_protocol_error,
    output wire         status_overflow,
    output wire         committed_valid,
    output wire         committed_bank
);
    wire signed [15:0] s_i = s_axis_iq_tdata[15:0];
    wire signed [15:0] s_q = s_axis_iq_tdata[31:16];

    // framer
    wire signed [15:0] win_i, win_q;
    wire               win_valid, win_last;
    wire               fft_ready;

    smart_scan_framer u_framer (
        .clk(clk), .rst_n(rst_n),
        .s_i(s_i), .s_q(s_q),
        .s_valid(s_axis_iq_tvalid), .s_ready(s_axis_iq_tready),
        .s_last(s_axis_iq_tlast),
        .m_i(win_i), .m_q(win_q),
        .m_valid(win_valid), .m_ready(fft_ready), .m_last(win_last)
    );

    // FFT
    wire signed [26:0] fft_re, fft_im;
    wire [9:0]         fft_index;
    wire               fft_valid, fft_last, fft_halt;
    wire               writer_ready;

    fft_vendor_ip_adapter u_fft (
        .clk(clk), .rst_n(rst_n),
        .s_i(win_i), .s_q(win_q),
        .s_valid(win_valid), .s_ready(fft_ready), .s_last(win_last),
        .m_re(fft_re), .m_im(fft_im),
        .m_index(fft_index), .m_valid(fft_valid),
        .m_ready(writer_ready), .m_last(fft_last), .data_halt(fft_halt)
    );

    // writer
    wire        wr_valid, wr_bank;
    wire [9:0]  wr_addr;
    wire [53:0] wr_power;
    wire        frame_done;
    wire [31:0] frame_id;
    wire        proto_err;

    fft_psd_stream_writer u_writer (
        .clk(clk), .rst_n(rst_n),
        .s_re(fft_re), .s_im(fft_im),
        .s_index(fft_index), .s_valid(fft_valid),
        .s_ready(writer_ready), .s_last(fft_last),
        .m_write_valid(wr_valid), .m_write_ready(1'b1),
        .m_write_bank(wr_bank), .m_write_addr(wr_addr),
        .m_write_power(wr_power), .frame_done(frame_done),
        .frame_id(frame_id), .protocol_error(proto_err)
    );

    // double buffer + readback + status
    smart_scan_psd_buffers u_buffers (
        .clk(clk), .rst_n(rst_n),
        .wr_valid(wr_valid), .wr_bank(wr_bank),
        .wr_addr(wr_addr), .wr_power(wr_power),
        .frame_id(frame_id), .protocol_error(proto_err), .overflow(fft_halt),
        .rd_bank(rd_bank), .rd_addr(rd_addr), .rd_data(rd_data),
        .version(version), .status_frame_id(status_frame_id),
        .status_protocol_error(status_protocol_error),
        .status_overflow(status_overflow),
        .committed_valid(committed_valid), .committed_bank(committed_bank)
    );
endmodule
