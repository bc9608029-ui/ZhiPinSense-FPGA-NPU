`timescale 1ns/1ps
// Post-FFT datapath only. The vendor FFT must output natural-order bins 0..1023.
// This module computes |X|^2, maps natural order to fftshift addresses, and
// writes one complete frame into alternating external buffers.
module fft_psd_stream_writer #(
    parameter integer FFT_LOG2 = 10,
    parameter integer FFT_BITS = 27,
    parameter integer POWER_BITS = 54
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire signed [FFT_BITS-1:0]   s_re,
    input  wire signed [FFT_BITS-1:0]   s_im,
    input  wire [FFT_LOG2-1:0]          s_index,
    input  wire                         s_valid,
    output wire                         s_ready,
    input  wire                         s_last,

    output reg                          m_write_valid,
    input  wire                         m_write_ready,
    output reg                          m_write_bank,
    output reg [FFT_LOG2-1:0]           m_write_addr,
    output reg [POWER_BITS-1:0]         m_write_power,
    output reg                          frame_done,
    output reg [31:0]                   frame_id,
    output reg                          protocol_error
);
    wire free = !m_write_valid || m_write_ready;
    assign s_ready = free;

    wire signed [(2*FFT_BITS)-1:0] re_square = s_re * s_re;
    wire signed [(2*FFT_BITS)-1:0] im_square = s_im * s_im;
    wire [POWER_BITS-1:0] power_u54 = $unsigned(re_square) + $unsigned(im_square);
    wire [FFT_LOG2-1:0] shifted_addr = s_index ^ ({{(FFT_LOG2-1){1'b0}},1'b1} << (FFT_LOG2-1));

    reg write_bank;
    reg m_write_last;
    reg [FFT_LOG2-1:0] expected_index;
    wire output_fire = m_write_valid && m_write_ready;
    wire frame_complete = output_fire && m_write_last;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            m_write_valid <= 1'b0;
            m_write_bank <= 1'b0;
            m_write_addr <= {FFT_LOG2{1'b0}};
            m_write_power <= {POWER_BITS{1'b0}};
            frame_done <= 1'b0;
            frame_id <= 32'd0;
            protocol_error <= 1'b0;
            write_bank <= 1'b0;
            m_write_last <= 1'b0;
            expected_index <= {FFT_LOG2{1'b0}};
        end else begin
            frame_done <= frame_complete;
            if (frame_complete) begin
                frame_id <= frame_id + 1'b1;
                write_bank <= ~write_bank;
            end
            if (free) begin
                m_write_valid <= s_valid;
                if (s_valid) begin
                    // A zero-gap next frame may arrive on the same cycle that
                    // the previous last output is consumed.
                    m_write_bank <= frame_complete ? ~write_bank : write_bank;
                    m_write_addr <= shifted_addr;
                    m_write_power <= power_u54;
                    m_write_last <= s_last;
                    if (s_index != expected_index)
                        protocol_error <= 1'b1;
                    if (s_last != (s_index == {FFT_LOG2{1'b1}}))
                        protocol_error <= 1'b1;
                    if (s_last) begin
                        expected_index <= {FFT_LOG2{1'b0}};
                    end else begin
                        expected_index <= expected_index + 1'b1;
                    end
                end
            end
        end
    end
endmodule
