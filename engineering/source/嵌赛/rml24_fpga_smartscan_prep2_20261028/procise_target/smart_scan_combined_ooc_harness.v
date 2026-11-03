`timescale 1ns/1ps
// Combined OOC harness: window -> migrated XFFT (fft_vendor_ip_adapter) ->
// u54 magnitude-square / fftshift / ping-pong writer, all in one Procise project
// on JFMQL30TAI676H. This is a P&R/STA smoke harness only, never a production
// top and never a board bitstream.
//
// The FFT input `last` is a 1-cycle-delayed frame mark. That is exactly aligned
// while the chain runs free (no backpressure stall). Under a real stall the
// production framer must carry `last` through the window pipeline (or gate the
// delay with the same valid/ready handshake) so it stays aligned with the data.
module smart_scan_combined_ooc_harness (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    output reg  [31:0] digest,
    output wire [31:0] completed_frames,
    output wire        protocol_error,
    output wire        active_bank
);
    reg [31:0] lfsr;
    reg [9:0]  sample_cnt;
    reg        s_last_r;

    wire signed [15:0] win_i, win_q;
    wire win_valid, win_ready;

    wire fft_s_ready;
    wire signed [26:0] fft_m_re, fft_m_im;
    wire [9:0] fft_m_index;
    wire fft_m_valid, fft_m_last;

    wire writer_ready;
    wire write_valid, write_bank;
    wire [9:0] write_addr;
    wire [53:0] write_power;
    wire frame_done;

    // Q1.15 unity window coefficient for the OOC smoke; the production Hann
    // coefficient table is added together with the framer.
    wire signed [15:0] s_w = 16'sd16384;

    wire s_valid = enable;
    wire s_last  = (sample_cnt == 10'd1023);

    window_mul_q15 u_window (
        .clk(clk), .rst_n(rst_n),
        .s_i(lfsr[15:0]), .s_q(lfsr[31:16]), .s_w(s_w),
        .s_valid(s_valid), .s_ready(win_ready),
        .m_i(win_i), .m_q(win_q), .m_valid(win_valid), .m_ready(fft_s_ready)
    );

    fft_vendor_ip_adapter u_fft (
        .clk(clk), .rst_n(rst_n),
        .s_i(win_i), .s_q(win_q),
        .s_valid(win_valid), .s_ready(fft_s_ready),
        .s_last(win_valid && s_last_r),
        .m_re(fft_m_re), .m_im(fft_m_im),
        .m_index(fft_m_index), .m_valid(fft_m_valid),
        .m_ready(1'b1), .m_last(fft_m_last)
    );

    // The external double-buffer write port is always ready in the OOC smoke.
    wire write_ready = 1'b1;

    fft_psd_stream_writer u_writer (
        .clk(clk), .rst_n(rst_n),
        .s_re(fft_m_re), .s_im(fft_m_im),
        .s_index(fft_m_index), .s_valid(fft_m_valid),
        .s_ready(writer_ready), .s_last(fft_m_last),
        .m_write_valid(write_valid), .m_write_ready(write_ready),
        .m_write_bank(write_bank), .m_write_addr(write_addr),
        .m_write_power(write_power), .frame_done(frame_done),
        .frame_id(completed_frames), .protocol_error(protocol_error)
    );

    assign active_bank = write_bank;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr <= 32'h1ace_b00c;
            sample_cnt <= 10'd0;
            s_last_r <= 1'b0;
            digest <= 32'd0;
        end else begin
            lfsr <= {lfsr[30:0], lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};
            if (s_valid && win_ready)
                sample_cnt <= (sample_cnt == 10'd1023) ? 10'd0 : sample_cnt + 1'b1;
            s_last_r <= s_last;
            digest <= digest
                ^ (win_valid ? ({{16{win_i[15]}}, win_i} ^ {win_q, win_q}) : 32'd0)
                ^ (fft_m_valid ? ({5'd0, fft_m_re} ^ {fft_m_im[26:0], fft_m_index[4:0]}) : 32'd0)
                ^ ((write_valid && write_ready)
                    ? (write_power[31:0] ^ {write_addr, write_power[53:32]}) : 32'd0);
        end
    end
endmodule
