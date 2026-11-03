`timescale 1ns/1ps
// OOC implementation harness only. It prevents internal FFT/PSD buses from
// becoming package pins while keeping the arithmetic and stream protocol live.
// This module is not a production top and must never be used as a board bitstream.
module smart_scan_postfft_ooc_harness(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    output reg  [31:0] digest,
    output wire [31:0] completed_frames,
    output wire        protocol_error,
    output wire        active_bank
);
    reg [31:0] lfsr;
    reg [9:0]  fft_index;

    wire signed [15:0] win_i;
    wire signed [15:0] win_q;
    wire win_valid;
    wire win_ready;

    window_mul_q15 u_window (
        .clk(clk), .rst_n(rst_n),
        .s_i(lfsr[15:0]), .s_q(lfsr[31:16]), .s_w(16'sd16384),
        .s_valid(enable), .s_ready(win_ready),
        .m_i(win_i), .m_q(win_q), .m_valid(win_valid), .m_ready(1'b1)
    );

    wire writer_ready;
    wire write_valid;
    wire write_ready = lfsr[0] | lfsr[5];
    wire write_bank;
    wire [9:0] write_addr;
    wire [53:0] write_power;
    wire frame_done;

    fft_psd_stream_writer u_writer (
        .clk(clk), .rst_n(rst_n),
        .s_re($signed({lfsr[26:0]})),
        .s_im($signed({lfsr[31:5]})),
        .s_index(fft_index),
        .s_valid(enable), .s_ready(writer_ready),
        .s_last(fft_index == 10'd1023),
        .m_write_valid(write_valid), .m_write_ready(write_ready),
        .m_write_bank(write_bank), .m_write_addr(write_addr),
        .m_write_power(write_power), .frame_done(frame_done),
        .frame_id(completed_frames), .protocol_error(protocol_error)
    );

    assign active_bank = write_bank;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr <= 32'h1ace_b00c;
            fft_index <= 10'd0;
            digest <= 32'd0;
        end else begin
            lfsr <= {lfsr[30:0], lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};
            if (enable && writer_ready) begin
                if (fft_index == 10'd1023)
                    fft_index <= 10'd0;
                else
                    fft_index <= fft_index + 1'b1;
            end
            if (win_valid)
                digest <= digest ^ {{16{win_i[15]}}, win_i}
                                 ^ {win_q, win_q};
            if (write_valid && write_ready)
                digest <= digest ^ write_power[31:0]
                                 ^ {write_addr, write_power[53:32]};
        end
    end
endmodule
